
import React, { useState, useEffect, useCallback } from 'react';
import { 
  View, 
  Text, 
  FlatList, 
  TouchableOpacity, 
  StyleSheet, 
  RefreshControl,
  Alert 
} from 'react-native';
import { getEngineerTasks } from '../api/api';
import { useAuth } from '../context/AuthContext';
import { sanitizeText } from '../utils/sanitize';
import { queryCache } from '../utils/cache';

const HOURS_24 = 24 * 60 * 60 * 1000;

const STATUS_PRIORITY = {
  'CREATED': 0,
  'ACTIVE': 1,
  'COMPLETED': 2,
  'CANCELLED': 3,
};

function filterVisibleTasks(tasks) {
  if (!Array.isArray(tasks)) return [];
  
  const now = new Date();
  return tasks.filter(task => {
    if (task.status !== 'COMPLETED') return true;
    const finishTime = task.completed_at || task.finished_at || task.updated_at || task.created_at;
    if (!finishTime) return true;
    return (now - new Date(finishTime)) < HOURS_24;
  });
}

function sortTasks(tasks) {
  return [...tasks].sort((a, b) => {
    const priorityA = STATUS_PRIORITY[a.status] ?? 99;
    const priorityB = STATUS_PRIORITY[b.status] ?? 99;
    
    if (priorityA !== priorityB) {
      return priorityA - priorityB;
    }
    
    const dateA = new Date(a.created_at || 0);
    const dateB = new Date(b.created_at || 0);
    return dateB - dateA;
  });
}

const TasksScreen = ({ navigation }) => {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [syncStatus, setSyncStatus] = useState('synced');
  
  const { logout } = useAuth();

  const loadTasks = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setError(null);
    setSyncStatus('syncing');
    
    try {
      // Используем кэш для получения задач
      const list = await queryCache.getOrFetch(
        'tasks',
        async () => {
          const response = await getEngineerTasks();
          
          let parsedList = [];
          
          if (response && typeof response === 'object') {
            if (Array.isArray(response.tasks)) {
              parsedList = response.tasks;
            } 
            else if (Array.isArray(response)) {
              parsedList = response;
            }
            else if (Array.isArray(response.data?.tasks)) {
              parsedList = response.data.tasks;
            }
            else if (Array.isArray(response.data)) {
              parsedList = response.data;
            }
          }
          
          if (!Array.isArray(parsedList)) {
            console.error('Invalid response format:', response);
            throw new Error('Неверный формат ответа сервера');
          }
          
          console.log('Tasks loaded:', parsedList.length);
          return parsedList;
        },
        30000 // TTL 30 секунд
      );
      
      setTasks(list);
      setLastUpdated(new Date());
      setSyncStatus('synced');
      setError(null);
    } catch (err) {
      console.error('loadTasks failed', err.message);
      setError(err.message || 'Не удалось загрузить задачи');
      setSyncStatus('stale');
      
      if (showLoading) {
        Alert.alert(
          'Ошибка загрузки',
          err.message || 'Не удалось обновить список задач. Показаны ранее загруженные данные.'
        );
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  useEffect(() => {
    const unsubscribe = navigation.addListener('focus', () => loadTasks(false));
    return unsubscribe;
  }, [navigation, loadTasks]);

  // Polling для real-time обновлений 
  useEffect(() => {
    const interval = setInterval(() => {
      if (!loading && !refreshing) {
        console.log('[Polling] Обновление задач в реальном времени');
        loadTasks(false);
      }
    }, 15000); // 15 секунд

    return () => clearInterval(interval);
  }, [loadTasks, loading, refreshing]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    queryCache.invalidate('tasks');
    loadTasks(false);
  }, [loadTasks]);

  const handleLogout = () => {
    Alert.alert(
      'Выход',
      'Вы уверены, что хотите выйти?',
      [
        { text: 'Отмена', style: 'cancel' },
        { 
          text: 'Выйти', 
          style: 'destructive',
          onPress: async () => {
            // Очищаем кэш при выходе
            queryCache.clear();
            await logout();
            navigation.replace('Login');
          }
        },
      ]
    );
  };

  const showErrorDetails = () => {
    if (error) {
      Alert.alert('Ошибка загрузки', error);
    }
  };

  const getStatusStyle = (status) => {
    switch (status) {
      case 'CREATED':
        return { bg: '#ffe4e1', text: '#d63384', label: 'Создана' };
      case 'ACTIVE':
        return { bg: '#fff3cd', text: '#856404', label: 'В работе' };
      case 'COMPLETED':
        return { bg: '#d4edda', text: '#155724', label: 'Выполнена' };
      case 'CANCELLED':
        return { bg: '#f8d7da', text: '#842029', label: 'Отменена' };
      default:
        return { bg: '#eee', text: '#666', label: status || 'Неизвестно' };
    }
  };

  const renderTask = ({ item }) => {
    const status = getStatusStyle(item.status);
    
    const displayFacility = item.facility_name 
      ? `${item.facility_name}${item.facility_address ? `, ${item.facility_address}` : ''}`
      : `Объект #${item.facility_id || '?'}`;
    
    return (
      <TouchableOpacity 
        style={styles.card} 
        onPress={() => navigation.navigate('TaskDetail', { 
          taskId: item.task_id,
          facilityName: item.facility_name,
          facilityAddress: item.facility_address,
        })}
      >
        <View style={styles.cardHeader}>
          <Text style={styles.facility} numberOfLines={1}>
            {sanitizeText(displayFacility)}
          </Text>
          <View style={[styles.badge, { backgroundColor: status.bg }]}>
            <Text style={[styles.badgeText, { color: status.text }]}>{status.label}</Text>
          </View>
        </View>
        
        <Text style={styles.description} numberOfLines={2}>
          {sanitizeText(item.description || item.operator_comment || 'Нет описания')}
        </Text>
        
        <Text style={styles.meta}>Заявка #{item.task_id} | Объект #{item.facility_id}</Text>
        
        <Text style={styles.date}>
          {item.created_at ? new Date(item.created_at).toLocaleDateString('ru-RU') : '-'}
        </Text>
      </TouchableOpacity>
    );
  };

  const renderError = () => {
    if (!error) return null;
    return (
      <TouchableOpacity style={styles.errorBox} onPress={showErrorDetails}>
        <Text style={styles.errorIcon}>⚠️</Text>
        <Text style={styles.errorText}>Ошибка загрузки</Text>
        <Text style={styles.errorSubtext}>Нажмите для подробностей</Text>
      </TouchableOpacity>
    );
  };

  const getSyncStatusStyle = () => {
    switch (syncStatus) {
      case 'synced':
        return { color: '#28a745', text: 'Актуально' };
      case 'syncing':
        return { color: '#ffc107', text: 'Синхронизация...' };
      case 'stale':
        return { color: '#dc3545', text: 'Данные устарели' };
      default:
        return { color: '#999', text: '?' };
    }
  };

  const visibleTasks = sortTasks(filterVisibleTasks(tasks));
  const hiddenCount = tasks.length - filterVisibleTasks(tasks).length;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Мои задачи</Text>
        
        <TouchableOpacity 
          style={styles.logoutButton} 
          onPress={handleLogout}
          activeOpacity={0.7}
        >
          <Text style={styles.logoutText}>Выйти</Text>
        </TouchableOpacity>
        
        <View style={styles.syncContainer}>
          <Text style={[styles.syncText, { color: getSyncStatusStyle().color }]}>
            {getSyncStatusStyle().text}
          </Text>
        </View>
        
        {lastUpdated && !error && (
          <Text style={styles.lastUpdated}>
            Обновлено: {lastUpdated.toLocaleTimeString('ru-RU')}
          </Text>
        )}
        
        {hiddenCount > 0 && (
          <Text style={styles.hiddenText}>
            {hiddenCount} выполненных задач скрыто (старше 24ч)
          </Text>
        )}
      </View>

      {renderError()}

      <FlatList 
        data={visibleTasks}
        renderItem={renderTask} 
        keyExtractor={(item) => item.task_id?.toString() || Math.random().toString()}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            colors={['#1a3a5c']}
            tintColor="#1a3a5c"
          />
        }
        ListEmptyComponent={
          !loading && !error ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon}>📋</Text>
              <Text style={styles.emptyText}>Нет задач</Text>
              <Text style={styles.emptySubtext}>Потяните вниз для обновления</Text>
            </View>
          ) : null
        }
      />

      {loading && !refreshing ? (
        <View style={styles.loadingOverlay}>
          <Text style={styles.loading}>Загрузка...</Text>
        </View>
      ) : null}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a3a5c',
  },
  header: {
    padding: 16,
    paddingTop: 44,
    alignItems: 'center',
    position: 'relative',
  },
  headerTitle: {
    color: 'white',
    fontSize: 18,
    fontWeight: 'bold',
  },
  logoutButton: {
    position: 'absolute',
    right: 16,
    top: 44,
    paddingVertical: 4,
    paddingHorizontal: 10,
    backgroundColor: 'rgba(255, 255, 255, 0.15)',
    borderRadius: 6,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.3)',
  },
  logoutText: {
    color: 'white',
    fontSize: 12,
    fontWeight: '600',
  },
  syncContainer: {
    marginTop: 2,
  },
  syncText: {
    fontSize: 11,
    fontWeight: '600',
  },
  lastUpdated: {
    color: 'rgba(255,255,255,0.6)',
    fontSize: 10,
    marginTop: 2,
  },
  hiddenText: {
    color: 'rgba(255,255,255,0.5)',
    fontSize: 10,
    marginTop: 2,
  },
  list: {
    padding: 8,
    paddingBottom: 20,
  },
  card: {
    backgroundColor: 'white',
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 6,
  },
  facility: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#1a3a5c',
    flex: 1,
    marginRight: 8,
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: 'bold',
  },
  description: {
    color: '#666',
    fontSize: 13,
    marginBottom: 6,
  },
  date: {
    color: '#999',
    fontSize: 11,
  },
  errorBox: {
    backgroundColor: '#f8d7da',
    margin: 8,
    marginTop: 0,
    padding: 12,
    borderRadius: 10,
    alignItems: 'center',
    borderLeftWidth: 4,
    borderLeftColor: '#dc3545',
  },
  errorIcon: {
    fontSize: 20,
    marginBottom: 2,
  },
  errorText: {
    color: '#842029',
    fontSize: 13,
    fontWeight: 'bold',
  },
  errorSubtext: {
    color: '#842029',
    fontSize: 11,
    opacity: 0.8,
    marginTop: 2,
  },
  emptyContainer: {
    alignItems: 'center',
    marginTop: 40,
  },
  emptyIcon: {
    fontSize: 40,
    marginBottom: 8,
  },
  emptyText: {
    color: 'white',
    fontSize: 15,
    fontWeight: 'bold',
  },
  emptySubtext: {
    color: 'rgba(255,255,255,0.6)',
    fontSize: 13,
    marginTop: 4,
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(26, 58, 92, 0.8)',
  },
  loading: {
    color: 'white',
    fontSize: 15,
  },
  meta: {
    color: '#aaa',
    fontSize: 10,
    marginTop: 3,
  },
});

export default TasksScreen;