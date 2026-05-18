import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useChatStore } from '../store/chatStore';

const SettingsScreen = () => {
  const { messages, liveMode, setLiveMode, clearMessages } = useChatStore();

  const handleClearChat = () => {
    Alert.alert(
      'Clear Chat History',
      'Are you sure you want to delete all messages?',
      [
        { text: 'Cancel', onPress: () => {}, style: 'cancel' },
        {
          text: 'Clear',
          onPress: clearMessages,
          style: 'destructive',
        },
      ]
    );
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Settings</Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Chat Settings</Text>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Ionicons name="radio" size={20} color="#00d4ff" />
            <View style={styles.settingText}>
              <Text style={styles.settingLabel}>Live Mode</Text>
              <Text style={styles.settingDescription}>
                Stream responses in real-time
              </Text>
            </View>
          </View>
          <Switch
            value={liveMode}
            onValueChange={setLiveMode}
            trackColor={{ false: '#444', true: '#00d4ff' }}
            thumbColor={liveMode ? '#00d4ff' : '#888'}
          />
        </View>

        <View style={styles.settingItem}>
          <View style={styles.settingInfo}>
            <Ionicons name="chatbubbles" size={20} color="#00d4ff" />
            <View style={styles.settingText}>
              <Text style={styles.settingLabel}>Chat History</Text>
              <Text style={styles.settingDescription}>
                {messages.length} messages
              </Text>
            </View>
          </View>
          <TouchableOpacity
            style={styles.clearButton}
            onPress={handleClearChat}
          >
            <Ionicons name="trash-outline" size={20} color="#ff4444" />
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About</Text>

        <View style={styles.aboutItem}>
          <Text style={styles.aboutLabel}>JARVIS Chat Mobile</Text>
          <Text style={styles.aboutValue}>Version 1.0.0</Text>
        </View>

        <View style={styles.aboutItem}>
          <Text style={styles.aboutLabel}>Backend</Text>
          <Text style={styles.aboutValue}>FastAPI + Ollama</Text>
        </View>

        <View style={styles.aboutItem}>
          <Text style={styles.aboutLabel}>Supported Models</Text>
          <Text style={styles.aboutValue}>50+ APIs & Local</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Features</Text>

        <View style={styles.featureList}>
          <View style={styles.featureItem}>
            <Ionicons name="radio" size={18} color="#00d4ff" />
            <Text style={styles.featureText}>Live streaming responses</Text>
          </View>
          <View style={styles.featureItem}>
            <Ionicons name="settings" size={18} color="#00d4ff" />
            <Text style={styles.featureText}>Multiple model support</Text>
          </View>
          <View style={styles.featureItem}>
            <Ionicons name="cloud-offline" size={18} color="#00d4ff" />
            <Text style={styles.featureText}>Local Ollama integration</Text>
          </View>
          <View style={styles.featureItem}>
            <Ionicons name="swap-vertical" size={18} color="#00d4ff" />
            <Text style={styles.featureText}>Instant model switching</Text>
          </View>
          <View style={styles.featureItem}>
            <Ionicons name="shield-checkmark" size={18} color="#00d4ff" />
            <Text style={styles.featureText}>Privacy-first architecture</Text>
          </View>
        </View>
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerText}>
          JARVIS © 2025 • Built with React Native
        </Text>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a0a',
  },
  header: {
    backgroundColor: '#1a1a1a',
    paddingHorizontal: 16,
    paddingVertical: 16,
    borderBottomColor: '#333',
    borderBottomWidth: 1,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
  },
  section: {
    marginHorizontal: 12,
    marginTop: 16,
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    overflow: 'hidden',
    borderColor: '#333',
    borderWidth: 1,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#00d4ff',
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  settingItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopColor: '#333',
    borderTopWidth: 1,
  },
  settingInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    gap: 12,
  },
  settingText: {
    flex: 1,
  },
  settingLabel: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '500',
  },
  settingDescription: {
    color: '#888',
    fontSize: 12,
    marginTop: 2,
  },
  clearButton: {
    padding: 8,
  },
  aboutItem: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopColor: '#333',
    borderTopWidth: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  aboutLabel: {
    color: '#888',
    fontSize: 14,
  },
  aboutValue: {
    color: '#00d4ff',
    fontSize: 14,
    fontWeight: '600',
  },
  featureList: {
    paddingHorizontal: 16,
    paddingBottom: 16,
  },
  featureItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 10,
    borderTopColor: '#333',
    borderTopWidth: 1,
  },
  featureText: {
    color: '#aaa',
    fontSize: 14,
    flex: 1,
  },
  footer: {
    paddingVertical: 32,
    alignItems: 'center',
  },
  footerText: {
    color: '#666',
    fontSize: 12,
  },
});

export default SettingsScreen;
