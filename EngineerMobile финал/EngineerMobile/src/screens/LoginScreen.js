import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Keyboard,
  TouchableWithoutFeedback,
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { employeeLogin, getMe } from '../api/api';

const LoginScreen = ({ navigation }) => {
  const [employeeKey, setEmployeeKey] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const passwordInputRef = useRef(null);
  const { login } = useAuth();

  // Санитизация ввода для защиты от XSS и инъекций
  const sanitizeInput = (text) => {
    if (!text) return '';

    return text
      .replace(/[<>]/g, '')
      .replace(/["'`]/g, '')
      .replace(/[;&|${}]/g, '')
      .replace(/\\/g, '')
      .replace(/javascript:/gi, '')
      .replace(/vbscript:/gi, '')
      .replace(/data:/gi, '')
      .replace(/on\w+=/gi, '')
      .replace(/onerror=/gi, '')
      .replace(/onload=/gi, '')
      .replace(/eval\(/gi, '')
      .replace(/expression\(/gi, '')
      .replace(/alert\(/gi, '')
      .replace(/confirm\(/gi, '')
      .replace(/prompt\(/gi, '')
      .trim();
  };

  const handleLogin = async () => {
    Keyboard.dismiss();

    if (!employeeKey || !password) {
      Alert.alert('Ошибка', 'Введите employee_key и password');
      return;
    }

    const sanitizedKey = sanitizeInput(employeeKey);
    if (sanitizedKey.length === 0) {
      Alert.alert('Ошибка', 'employee_key содержит недопустимые символы');
      return;
    }

    if (sanitizedKey.length < 3) {
      Alert.alert('Ошибка', 'employee_key слишком короткий');
      return;
    }

    if (sanitizedKey.length > 100) {
      Alert.alert('Ошибка', 'employee_key слишком длинный');
      return;
    }

    setLoading(true);
    try {
      const auth = await employeeLogin(sanitizedKey, password);
      const me = await getMe();

      await login(auth.access_token, {
        id: me.subject_id,
        roles: me.roles || [],
        account_type: me.account_type,
        email: me.email,
        employee_key: me.employee_key,
      });

      navigation.replace('Tasks');
    } catch (err) {
      const errorMessage = err.message || '';

      if (errorMessage.includes('<!DOCTYPE') || errorMessage.includes('<html')) {
        console.log('Server unavailable (ngrok/network error)');
      } else {
        console.log('Login error:', errorMessage);
      }

      let userMessage = 'Не удалось подключиться к серверу';

      if (err.status === 401) {
        userMessage = 'Неверный employee_key или пароль';
      } else if (err.status === 429) {
        userMessage = 'Слишком много попыток входа. Подождите немного.';
      } else if (err.status === 403) {
        userMessage = 'Доступ запрещён. Обратитесь к администратору.';
      } else if (err.status === 404) {
        userMessage = 'Сервер не найден. Проверьте подключение.';
      } else if (err.status === 409) {
        userMessage = 'Недопустимый переход статуса';
      } else if (err.status >= 500) {
        userMessage = 'Ошибка сервера. Попробуйте позже.';
      } else if (errorMessage.includes('Network') || errorMessage.includes('network') || errorMessage.includes('fetch')) {
        userMessage = 'Нет подключения к интернету. Проверьте сеть.';
      } else if (errorMessage.includes('<!DOCTYPE') || errorMessage.includes('<html')) {
        userMessage = 'Сервер временно недоступен. Проверьте подключение.';
      }

      Alert.alert('Ошибка входа', userMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : -100}
      >
        <TouchableWithoutFeedback onPress={Keyboard.dismiss}>
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
            bounces={false}
          >
            {/* Логотип - уменьшенный отступ сверху */}
            <View style={styles.logoContainer}>
              <View style={styles.logoCircle}>
                <Text style={styles.logoIcon}>🏗️</Text>
              </View>
            </View>

            <Text style={styles.appName}>Engineer Mobile</Text>
            <Text style={styles.title}>Мониторинг спортивных сооружений</Text>

            {/* Форма - добавлен marginBottom для отступа при клавиатуре */}
            <View style={styles.form}>
              <Text style={styles.inputLabel}>employee_key</Text>
              <TextInput
                style={styles.input}
                placeholder="Введите employee_key"
                placeholderTextColor="#999"
                value={employeeKey}
                onChangeText={(text) => setEmployeeKey(sanitizeInput(text))}
                autoCapitalize="none"
                autoCorrect={false}
                autoComplete="off"
                editable={!loading}
                returnKeyType="next"
                blurOnSubmit={false}
                onSubmitEditing={() => passwordInputRef.current?.focus()}
              />

              <Text style={styles.inputLabel}>password</Text>
              <TextInput
                ref={passwordInputRef}
                style={styles.input}
                placeholder="Введите пароль"
                placeholderTextColor="#999"
                value={password}
                onChangeText={(text) => setPassword(sanitizeInput(text))}
                secureTextEntry
                autoCapitalize="none"
                autoCorrect={false}
                autoComplete="off"
                editable={!loading}
                returnKeyType="done"
                onSubmitEditing={handleLogin}
              />

              <TouchableOpacity
                style={[styles.button, loading && styles.buttonDisabled]}
                onPress={handleLogin}
                disabled={loading}
                activeOpacity={0.8}
              >
                <Text style={styles.buttonText}>
                  {loading ? 'Вход...' : 'Войти'}
                </Text>
              </TouchableOpacity>
            </View>
            
            {}
            <View style={styles.bottomPadding} />
          </ScrollView>
        </TouchableWithoutFeedback>
      </KeyboardAvoidingView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a3a5c',
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: 24,
    paddingTop: 40,
    paddingBottom: 40,
  },
  logoContainer: {
    alignItems: 'center',
    marginBottom: 16,
  },
  logoCircle: {
    width: 70,
    height: 70,
    borderRadius: 35,
    backgroundColor: 'white',
    justifyContent: 'center',
    alignItems: 'center',
  },
  logoIcon: {
    fontSize: 36,
  },
  appName: {
    color: 'white',
    fontSize: 26,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 6,
  },
  title: {
    color: 'white',
    fontSize: 15,
    fontWeight: '500',
    textAlign: 'center',
    marginBottom: 28,
    opacity: 0.9,
  },
  form: {
    backgroundColor: 'white',
    borderRadius: 20,
    padding: 24,
    width: '100%',
    marginBottom: 20,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 4,
    },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 6,
  },
  inputLabel: {
    fontSize: 14,
    color: '#555',
    marginBottom: 8,
    fontWeight: '600',
  },
  input: {
    borderWidth: 1,
    borderColor: '#e0e0e0',
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 16,
    marginBottom: 20,
    fontSize: 16,
    color: '#333',
    backgroundColor: '#fafafa',
  },
  button: {
    backgroundColor: '#1a3a5c',
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonDisabled: {
    opacity: 0.6,
    backgroundColor: '#66809e',
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: 'bold',
  },
  bottomPadding: {
    height: Platform.OS === 'ios' ? 30 : 50,
  },
});

export default LoginScreen;