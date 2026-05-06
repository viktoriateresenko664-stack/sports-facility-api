import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ScrollView,
  ActivityIndicator,
  Platform,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  getEngineerTask,
  startEngineerTask,
  finishEngineerTask,
  uploadReport,
} from '../api/api';
import { API_BASE_URL } from '../api/api';
import * as DocumentPicker from 'expo-document-picker';
import { File, Directory, Paths } from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import { sanitizeText } from '../utils/sanitize';
import { queryCache } from '../utils/cache';

const DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

const getTemplateFile = () => new File(Paths.cache, 'engineer_report_template.docx');
const getTemplateMetaFile = () => new File(Paths.cache, 'engineer_report_template.meta.json');

async function readTemplateMeta() {
  try {
    const metaFile = getTemplateMetaFile();
    const info = await metaFile.info();
    if (!info.exists) return null;
    return JSON.parse(metaFile.textSync());
  } catch {
    return null;
  }
}

async function writeTemplateMeta(meta) {
  const metaFile = getTemplateMetaFile();
  await metaFile.write(JSON.stringify(meta));
}

async function ensureCachedTemplate(token, baseUrl) {
  const headers = {
    'Authorization': `Bearer ${token}`,
    'ngrok-skip-browser-warning': 'true',
  };

  const headRes = await fetch(`${baseUrl}/reports/template`, {
    method: 'HEAD',
    headers,
  });

  const serverMeta = {
    etag: headRes.headers.get('etag'),
    lastModified: headRes.headers.get('last-modified'),
  };

  const localMeta = await readTemplateMeta();
  const templateFile = getTemplateFile();
  const localFile = await templateFile.info();

  const sameVersion = localFile.exists &&
    localMeta?.etag === serverMeta.etag &&
    localMeta?.lastModified === serverMeta.lastModified;

  if (!sameVersion) {
    if (localFile.exists) {
      await templateFile.delete();
    }
    
    const tempFile = new File(Paths.cache, `template_download_${Date.now()}.docx`);
    
    const output = await File.downloadFileAsync(
      `${baseUrl}/reports/template`,
      tempFile,
      { headers }
    );
    
    const downloadedInfo = await output.info();
    if (!downloadedInfo.exists) {
      throw new Error(`GET /reports/template failed: file not downloaded`);
    }
    
    await output.copy(templateFile);

    await output.delete();
    
    await writeTemplateMeta(serverMeta);
  }

  return templateFile.uri;
}

async function createReportDraft(token, baseUrl, taskId) {
  const templatePath = await ensureCachedTemplate(token, baseUrl);
  const templateFile = getTemplateFile();
  const draftFile = new File(
    Paths.document, 
    `report_task_${taskId}_${Date.now()}.docx`
  );
  await templateFile.copy(draftFile);
  return draftFile.uri;
}

const TaskDetailScreen = ({ route, navigation }) => {
  const { taskId, facilityName, facilityAddress } = route.params;

  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(true);
  const [attachedFile, setAttachedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  
  const [localStatus, setLocalStatus] = useState(null);
  const [syncPending, setSyncPending] = useState(false);

  useEffect(() => {
    loadTask();
  }, []);

  const loadTask = async () => {
    try {
      const found = await getEngineerTask(taskId);
      console.log('--- FULL TASK DATA ---');
      console.log(JSON.stringify(found, null, 2));
      console.log('----------------------');
      
      setTask(found || null);
      
      if (localStatus && found?.status === localStatus) {
        setSyncPending(false);
        setLocalStatus(null);
      }
    } catch (err) {
      console.error('loadTask failed', err.message);
    } finally {
      setLoading(false);
    }
  };

  const waitForStatusUpdate = async (expectedStatus, maxAttempts = 6) => {
    let attempts = 0;
    
    const check = async () => {
      attempts++;
      await loadTask();
      
      const currentStatus = task?.status || localStatus;
      if (currentStatus === expectedStatus) {
        setSyncPending(false);
        return true;
      }
      
      if (attempts < maxAttempts) {
        setTimeout(check, 500);
        return false;
      }
      
      setSyncPending(false);
      return false;
    };
    
    return new Promise((resolve) => {
      const timeout = setTimeout(async () => {
        const result = await check();
        clearTimeout(timeout);
        resolve(result);
      }, 500);
    });
  };

  const handleStart = async () => {
    setActionLoading(true);
    setSyncPending(true);
    
    try {
      await startEngineerTask(taskId);
      
      // Инвалидируем кэш списка задач после команды
      queryCache.invalidate('tasks');
      
      const updated = await waitForStatusUpdate('ACTIVE', 6);
      
      if (updated) {
        Alert.alert('Успех', 'Задача начата');
      } else {
        Alert.alert('Внимание', 'Статус обновляется. Потяните вниз для обновления.');
      }
      
    } catch (err) {
      setSyncPending(false);
      Alert.alert('Ошибка', err.message || 'Не удалось начать задачу');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDownloadTemplate = async () => {
    setActionLoading(true);
    
    try {
      const token = await AsyncStorage.getItem('token');
      const baseUrl = API_BASE_URL;
      const draftPath = await createReportDraft(token, baseUrl, taskId);
      
      const canShare = await Sharing.isAvailableAsync();
      if (!canShare) {
        Alert.alert('Ошибка', 'Шаринг не доступен на этом устройстве');
        setActionLoading(false);
        return;
      }
      
      Alert.alert(
        'Создание отчёта',
        'Будет создан черновик отчёта. После заполнения вернитесь в приложение и прикрепите файл.',
        [
          { text: 'Отмена', style: 'cancel' },
          {
            text: 'Создать отчёт',
            onPress: async () => {
              await Sharing.shareAsync(draftPath, {
                mimeType: DOCX_MIME,
                dialogTitle: 'Заполните отчёт',
              });
              Alert.alert(
                'Готово',
                'После заполнения отчёта нажмите "Прикрепить файл" и выберите заполненный документ'
              );
            }
          }
        ]
      );
      
    } catch (err) {
      console.error('Download template error:', err);
      Alert.alert('Ошибка', err.message || 'Не удалось создать черновик отчёта');
    } finally {
      setActionLoading(false);
    }
  };

  const handleAttachFile = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: DOCX_MIME,
        copyToCacheDirectory: true,
      });

      if (result.canceled === false && result.assets && result.assets.length > 0) {
        const file = result.assets[0];
        
        console.log('=== SELECTED FILE ===');
        console.log('URI:', file.uri);
        console.log('Name:', file.name);
        console.log('Size:', file.size);
        console.log('MimeType:', file.mimeType);
        
        setAttachedFile({
          uri: file.uri,
          name: file.name,
          size: file.size,
          mimeType: file.mimeType,
        });
        Alert.alert('Файл выбран', `Имя: ${file.name}\nРазмер: ${(file.size / 1024).toFixed(1)} КБ`);
      }
    } catch (error) {
      console.error('DocumentPicker error:', error);
      Alert.alert('Ошибка', 'Не удалось выбрать файл');
    }
  };

  const handleComplete = async () => {
    if (!attachedFile) {
      Alert.alert('Ошибка', 'Сначала прикрепите заполненный отчёт');
      return;
    }

    setUploading(true);
    setSyncPending(true);
    
    try {
      let fileToUpload = attachedFile;
      
      if (attachedFile.uri.startsWith('content://')) {
        const fileName = attachedFile.name || `report_${Date.now()}`;
        const tempFile = new File(Paths.cache, fileName);

        const sourceFile = new File(attachedFile.uri);
        await sourceFile.copy(tempFile);
        
        fileToUpload = {
          ...attachedFile,
          uri: tempFile.uri,
        };
      }
      
      await uploadReport(taskId, fileToUpload);
      await finishEngineerTask(taskId);

      queryCache.invalidate('tasks');
      
      const updated = await waitForStatusUpdate('COMPLETED', 6);
      
      if (updated) {
        setAttachedFile(null);
        Alert.alert('Успех', 'Отчёт загружен. Задача выполнена.');
        
        if (attachedFile.uri.startsWith('content://')) {
          const tempFile = new File(fileToUpload.uri);
          await tempFile.delete();
        }
      } else {
        Alert.alert('Внимание', 'Задача завершена, данные обновляются.');
      }
      
    } catch (err) {
      setSyncPending(false);
      Alert.alert('Ошибка', err.message || 'Не удалось загрузить отчёт');
    } finally {
      setUploading(false);
    }
  };

  if (loading) return (
    <View style={styles.container}>
      <Text style={styles.loading}>Загрузка...</Text>
    </View>
  );
  
  if (!task) return (
    <View style={styles.container}>
      <Text style={styles.loading}>Задача не найдена</Text>
    </View>
  );

  const displayStatus = localStatus || task.status;
  const isCreated = displayStatus === 'CREATED';
  const isActive = displayStatus === 'ACTIVE';
  const isCompleted = displayStatus === 'COMPLETED';

  const getStatusStyle = () => {
    if (isActive) return { bg: '#fff3cd', text: '#856404', label: 'В работе' };
    if (isCompleted) return { bg: '#d4edda', text: '#155724', label: 'Выполнена' };
    return { bg: '#ffe4e1', text: '#d63384', label: 'Создана' };
  };

  const statusStyle = getStatusStyle();

  return (
    <View style={styles.container}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.back}>
          <Text style={styles.backText}>← Назад</Text>
        </TouchableOpacity>

        {syncPending && (
          <View style={styles.syncBanner}>
            <ActivityIndicator size="small" color="#ffc107" />
            <Text style={styles.syncBannerText}>Синхронизация...</Text>
          </View>
        )}

        <View style={styles.card}>
          <Text style={styles.title}>Заявка #{task.task_id || task.id || '?'}</Text>
          <Text style={styles.subtitle}>
            {sanitizeText(facilityAddress || task.facility_address || `Объект #${task.facility_id || '?'}`)}
          </Text>
          {facilityName || task.facility_name ? (
            <Text style={styles.address}>{sanitizeText(facilityName || task.facility_name)}</Text>
          ) : null}

          <View style={styles.divider} />

          <View style={styles.section}>
            <Text style={styles.label}>Описание проблемы</Text>
            <Text style={styles.value}>
              {sanitizeText(task.description || task.request_description || 'Нет описания')}
            </Text>
          </View>

          <View style={styles.section}>
            <Text style={styles.label}>Статус</Text>
            <View style={[styles.statusBadge, { backgroundColor: statusStyle.bg }]}>
              <Text style={[styles.statusText, { color: statusStyle.text }]}>
                {statusStyle.label}
              </Text>
            </View>
          </View>

          {task.operator_comment ? (
            <View style={styles.section}>
              <Text style={styles.label}>Комментарий оператора</Text>
              <Text style={styles.value}>{sanitizeText(task.operator_comment)}</Text>
            </View>
          ) : null}

          <View style={styles.section}>
            <Text style={styles.label}>Информация</Text>
            {task.created_at && <Text style={styles.metaText}>Создана: {new Date(task.created_at).toLocaleString('ru-RU')}</Text>}
            {task.started_at && <Text style={styles.metaText}>Начата: {new Date(task.started_at).toLocaleString('ru-RU')}</Text>}
            {task.completed_at && <Text style={styles.metaText}>Завершена: {new Date(task.completed_at).toLocaleString('ru-RU')}</Text>}
          </View>

          {task.sensors && Object.keys(task.sensors).length > 0 && (
            <View style={styles.section}>
              <Text style={styles.label}>Параметры датчиков:</Text>
              {Object.entries(task.sensors).map(([key, value]) => (
                <Text key={key} style={styles.sensorValue}>
                  {`${sanitizeText(key)}: ${sanitizeText(String(value))}`}
                </Text>
              ))}
            </View>
          )}
        </View>

        <View style={styles.actions}>
          {isCreated && (
            <TouchableOpacity 
              style={[styles.btnPrimary, syncPending && styles.btnDisabled]} 
              onPress={handleStart} 
              disabled={actionLoading || syncPending}
            >
              <Text style={styles.btnPrimaryText}>
                {actionLoading ? '...' : syncPending ? 'Ожидание...' : 'Взяться за работу'}
              </Text>
            </TouchableOpacity>
          )}

          {isActive && (
            <>
              <TouchableOpacity 
                style={styles.btnSecondary} 
                onPress={handleDownloadTemplate}
                disabled={actionLoading}
              >
                <Text style={styles.btnSecondaryText}>
                  {actionLoading ? 'Загрузка...' : 'Создать отчёт'}
                </Text>
              </TouchableOpacity>

              <TouchableOpacity style={styles.btnSecondary} onPress={handleAttachFile}>
                <Text style={styles.btnSecondaryText}>Прикрепить заполненный отчёт</Text>
              </TouchableOpacity>

              {attachedFile && (
                <View style={styles.attachedFile}>
                  <Text style={styles.attachedFileText}>Файл: {sanitizeText(attachedFile.name)}</Text>
                </View>
              )}

              <TouchableOpacity 
                style={[styles.btnSuccess, uploading && styles.btnDisabled]} 
                onPress={handleComplete} 
                disabled={uploading}
              >
                <Text style={styles.btnSuccessText}>
                  {uploading ? 'Загрузка...' : 'Завершить задачу'}
                </Text>
              </TouchableOpacity>
            </>
          )}

          {isCompleted && (
            <View style={styles.completedBox}>
              <Text style={styles.completedText}>Задача выполнена</Text>
            </View>
          )}
        </View>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a3a5c',
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
    paddingTop: 44,
    paddingBottom: 30,
  },
  back: {
    marginBottom: 12,
  },
  backText: {
    color: 'white',
    fontSize: 14,
  },
  syncBanner: {
    backgroundColor: 'rgba(255, 193, 7, 0.2)',
    borderWidth: 1,
    borderColor: '#ffc107',
    borderRadius: 6,
    padding: 8,
    marginBottom: 12,
    flexDirection: 'row',
    alignItems: 'center',
  },
  syncBannerText: {
    color: '#ffc107',
    marginLeft: 8,
    fontSize: 12,
    fontWeight: '600',
  },
  card: {
    backgroundColor: 'white',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  title: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#1a3a5c',
    marginBottom: 2,
  },
  subtitle: {
    fontSize: 15,
    color: '#333',
    marginBottom: 2,
    fontWeight: '600',
  },
  address: {
    fontSize: 13,
    color: '#666',
    marginBottom: 6,
  },
  divider: {
    height: 1,
    backgroundColor: '#eee',
    marginVertical: 12,
  },
  section: {
    marginBottom: 14,
  },
  label: {
    color: '#666',
    fontSize: 12,
    marginBottom: 4,
    fontWeight: '600',
  },
  value: {
    fontSize: 14,
    color: '#333',
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    alignSelf: 'flex-start',
  },
  statusText: {
    fontSize: 11,
    fontWeight: 'bold',
  },
  sensorValue: {
    fontSize: 13,
    color: '#333',
    marginTop: 2,
  },
  metaText: {
    fontSize: 11,
    color: '#999',
    marginTop: 2,
  },
  actions: {
    marginBottom: 20,
  },
  btnPrimary: {
    backgroundColor: '#ffc107',
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 8,
  },
  btnPrimaryText: {
    color: '#333',
    fontSize: 14,
    fontWeight: 'bold',
  },
  btnSecondary: {
    backgroundColor: '#e9ecef',
    padding: 10,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 8,
  },
  btnSecondaryText: {
    color: '#1a3a5c',
    fontSize: 13,
  },
  btnSuccess: {
    backgroundColor: '#1a3a5c',
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 6,
  },
  btnSuccessText: {
    color: 'white',
    fontSize: 14,
    fontWeight: 'bold',
  },
  btnDisabled: {
    opacity: 0.6,
  },
  attachedFile: {
    backgroundColor: '#e8f4f8',
    padding: 8,
    borderRadius: 6,
    marginBottom: 8,
    borderLeftWidth: 3,
    borderLeftColor: '#1a3a5c',
  },
  attachedFileText: {
    color: '#1a3a5c',
    fontSize: 12,
  },
  completedBox: {
    backgroundColor: 'white',
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  completedText: {
    color: '#28a745',
    fontSize: 14,
    fontWeight: 'bold',
  },
  loading: {
    color: 'white',
    fontSize: 14,
    textAlign: 'center',
    marginTop: 40,
  },
});

export default TaskDetailScreen;