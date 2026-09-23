import React, { useState, useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ActivityIndicator,
  SafeAreaView,
  ScrollView,
} from 'react-native';
import { fetchHealthCheck, fetchRootStatus, API_BASE_URL } from './api';

export default function App() {
  const [loading, setLoading] = useState(false);
  const [backendData, setBackendData] = useState(null);
  const [healthData, setHealthData] = useState(null);
  const [error, setError] = useState(null);

  const checkConnection = async () => {
    setLoading(true);
    setError(null);
    try {
      const [rootRes, healthRes] = await Promise.all([
        fetchRootStatus(),
        fetchHealthCheck(),
      ]);
      setBackendData(rootRes);
      setHealthData(healthRes);
    } catch (err) {
      setError(err.message || 'Không thể kết nối đến FastAPI Backend');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkConnection();
  }, []);

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="light" />
      <ScrollView contentContainerStyle={styles.container}>
        {/* Header */}
        <View style={styles.headerContainer}>
          <Text style={styles.badgeText}>🔥 Project AI Cooking</Text>
          <Text style={styles.title}>React Native + FastAPI</Text>
          <Text style={styles.subtitle}>Fullstack Mobile App Architecture</Text>
        </View>

        {/* Status Card */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.cardTitle}>⚡ Server Status</Text>
            <View
              style={[
                styles.statusDot,
                { backgroundColor: backendData ? '#10B981' : error ? '#EF4444' : '#F59E0B' },
              ]}
            />
          </View>

          <Text style={styles.label}>Backend Endpoint:</Text>
          <Text style={styles.codeText}>{API_BASE_URL}</Text>

          {loading ? (
            <View style={styles.loadingBox}>
              <ActivityIndicator size="large" color="#6366F1" />
              <Text style={styles.loadingText}>Đang kiểm tra kết nối server...</Text>
            </View>
          ) : error ? (
            <View style={styles.errorBox}>
              <Text style={styles.errorTitle}>❌ Lỗi Kết Nối</Text>
              <Text style={styles.errorText}>{error}</Text>
              <Text style={styles.errorHint}>
                Hãy chắc chắn backend FastAPI đang khởi chạy ở port 8000.
              </Text>
            </View>
          ) : (
            <View style={styles.successBox}>
              <Text style={styles.successTitle}>✅ Đã kết nối thành công!</Text>
              {backendData && (
                <View style={styles.infoRow}>
                  <Text style={styles.infoKey}>Thông điệp:</Text>
                  <Text style={styles.infoVal}>{backendData.message}</Text>
                </View>
              )}
              {backendData && (
                <View style={styles.infoRow}>
                  <Text style={styles.infoKey}>Phiên bản API:</Text>
                  <Text style={styles.infoVal}>v{backendData.version}</Text>
                </View>
              )}
              {healthData && (
                <View style={styles.infoRow}>
                  <Text style={styles.infoKey}>Trạng thái hệ thống:</Text>
                  <Text style={styles.infoVal}>{healthData.status} ({healthData.environment})</Text>
                </View>
              )}
            </View>
          )}

          {/* Action Button */}
          <TouchableOpacity
            style={styles.button}
            onPress={checkConnection}
            disabled={loading}
            activeOpacity={0.8}
          >
            <Text style={styles.buttonText}>
              {loading ? 'Đang tải...' : '🔄 Kiểm Tra Lại Kết Nối'}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Tech Stack Info Card */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>🚀 Tech Stack Configuration</Text>
          <View style={styles.techBadgeContainer}>
            <View style={[styles.techBadge, { backgroundColor: '#3178C6' }]}>
              <Text style={styles.techBadgeText}>React Native / Expo</Text>
            </View>
            <View style={[styles.techBadge, { backgroundColor: '#009688' }]}>
              <Text style={styles.techBadgeText}>Python FastAPI</Text>
            </View>
            <View style={[styles.techBadge, { backgroundColor: '#4B5563' }]}>
              <Text style={styles.techBadgeText}>Uvicorn Server</Text>
            </View>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#0F172A', // Sleek dark theme
  },
  container: {
    padding: 24,
    paddingTop: 40,
  },
  headerContainer: {
    marginBottom: 24,
    alignItems: 'center',
  },
  badgeText: {
    color: '#818CF8',
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: 1,
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    color: '#F8FAFC',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 14,
    color: '#94A3B8',
    marginTop: 4,
    textAlign: 'center',
  },
  card: {
    backgroundColor: '#1E293B',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#334155',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 5,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#F1F5F9',
  },
  statusDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
  },
  label: {
    fontSize: 12,
    color: '#64748B',
    marginBottom: 4,
    textTransform: 'uppercase',
    fontWeight: '600',
  },
  codeText: {
    fontFamily: 'monospace',
    backgroundColor: '#0F172A',
    color: '#38BDF8',
    padding: 10,
    borderRadius: 8,
    marginBottom: 16,
    fontSize: 14,
  },
  loadingBox: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  loadingText: {
    color: '#94A3B8',
    marginTop: 12,
    fontSize: 14,
  },
  errorBox: {
    backgroundColor: '#451A03',
    borderColor: '#78350F',
    borderWidth: 1,
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
  },
  errorTitle: {
    color: '#FDBA74',
    fontWeight: '700',
    fontSize: 15,
    marginBottom: 4,
  },
  errorText: {
    color: '#FED7AA',
    fontSize: 13,
    marginBottom: 6,
  },
  errorHint: {
    color: '#FB923C',
    fontSize: 12,
    fontStyle: 'italic',
  },
  successBox: {
    backgroundColor: '#064E3B',
    borderColor: '#065F46',
    borderWidth: 1,
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
  },
  successTitle: {
    color: '#6EE7B7',
    fontWeight: '700',
    fontSize: 15,
    marginBottom: 8,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 6,
  },
  infoKey: {
    color: '#A7F3D0',
    fontSize: 13,
  },
  infoVal: {
    color: '#ECFDF5',
    fontWeight: '600',
    fontSize: 13,
  },
  button: {
    backgroundColor: '#6366F1',
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
  },
  buttonText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 15,
  },
  techBadgeContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 12,
  },
  techBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
  },
  techBadgeText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: 12,
  },
});
