import React, { createContext, useEffect, useState, useContext } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getMe, logoutMobile } from '../api/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const restoreAuth = async () => {
      try {
        const savedToken = await AsyncStorage.getItem('token');
        if (!savedToken) {
          setIsLoading(false);
          return;
        }

        setToken(savedToken);
        const me = await getMe();
        setUser({
          id: me.subject_id,
          roles: me.roles || [],
          account_type: me.account_type,
          email: me.email,
          employee_key: me.employee_key,
        });
      } catch (error) {
        console.log('Auth restore error:', error.message);
        
        if (error.status === 401 || error.message.includes('revoked') || error.message.includes('Сессия истекла')) {
          console.log('Token invalid or revoked, clearing storage');
          await logoutMobile();
        }
        
        setUser(null);
        setToken(null);
      } finally {
        setIsLoading(false);
      }
    };

    restoreAuth();
  }, []);

  const login = async (newToken, userData) => {
    setToken(newToken);
    setUser(userData);
  };

  const logout = async () => {
    await logoutMobile();
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);