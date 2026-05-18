import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  TextInput,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useChatStore } from '../store/chatStore';
import { getClient } from '../api/client';

const AVAILABLE_MODELS = [
  {
    category: 'API Models',
    models: [
      { id: 'gemini/gemini-2.0-flash', name: 'Gemini 2.0 Flash', icon: 'star' },
      { id: 'claude-3-5-sonnet', name: 'Claude 3.5 Sonnet', icon: 'flash' },
      { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', icon: 'bulb' },
      { id: 'mistral/mistral-7b', name: 'Mistral 7B', icon: 'flame' },
    ],
  },
  {
    category: 'Local (Ollama)',
    models: [
      { id: 'ollama/llama2', name: 'Llama 2', icon: 'layers' },
      { id: 'ollama/mistral', name: 'Mistral', icon: 'layers' },
      { id: 'ollama/neural-chat', name: 'Neural Chat', icon: 'layers' },
      { id: 'ollama/dolphin-mixtral', name: 'Dolphin Mixtral', icon: 'layers' },
    ],
  },
];

const ModelsScreen = () => {
  const { selectedModel, serverUrl, setSelectedModel, setServerUrl } =
    useChatStore();

  const [customServerUrl, setCustomServerUrl] = useState(serverUrl);
  const [isLoadingHealth, setIsLoadingHealth] = useState(false);
  const [serverStatus, setServerStatus] = useState<'healthy' | 'offline' | null>(
    null
  );

  const client = getClient(serverUrl);

  const checkServerHealth = async () => {
    setIsLoadingHealth(true);
    try {
      await client.getHealth();
      setServerStatus('healthy');
    } catch (error) {
      setServerStatus('offline');
    } finally {
      setIsLoadingHealth(false);
    }
  };

  useEffect(() => {
    checkServerHealth();
  }, [serverUrl]);

  const handleModelSelect = (modelId: string) => {
    setSelectedModel(modelId);
  };

  const handleServerUrlChange = () => {
    if (customServerUrl.trim()) {
      setServerUrl(customServerUrl.trim());
    }
  };

  const renderModelItem = ({ item }) => (
    <TouchableOpacity
      style={[
        styles.modelItem,
        selectedModel === item.id && styles.modelItemSelected,
      ]}
      onPress={() => handleModelSelect(item.id)}
    >
      <View style={styles.modelIconContainer}>
        <Ionicons
          name={item.icon}
          size={24}
          color={selectedModel === item.id ? '#00d4ff' : '#888'}
        />
      </View>
      <View style={styles.modelInfo}>
        <Text style={styles.modelName}>{item.name}</Text>
        <Text style={styles.modelId}>{item.id}</Text>
      </View>
      {selectedModel === item.id && (
        <Ionicons name="checkmark-circle" size={24} color="#00d4ff" />
      )}
    </TouchableOpacity>
  );

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Models & Configuration</Text>
      </View>

      <View style={styles.serverSection}>
        <Text style={styles.sectionTitle}>Server Configuration</Text>
        <View style={styles.serverBox}>
          <TextInput
            style={styles.serverInput}
            placeholder="http://localhost:8501"
            placeholderTextColor="#666"
            value={customServerUrl}
            onChangeText={setCustomServerUrl}
            editable={!isLoadingHealth}
          />
          <TouchableOpacity
            style={styles.checkButton}
            onPress={handleServerUrlChange}
            disabled={isLoadingHealth}
          >
            {isLoadingHealth ? (
              <ActivityIndicator size="small" color="#00d4ff" />
            ) : (
              <Ionicons
                name="checkmark"
                size={20}
                color={serverStatus === 'healthy' ? '#00ff00' : '#888'}
              />
            )}
          </TouchableOpacity>
        </View>
        <View style={styles.statusRow}>
          <Text style={styles.statusLabel}>Server Status:</Text>
          <View
            style={[
              styles.statusBadge,
              {
                backgroundColor:
                  serverStatus === 'healthy'
                    ? '#00ff0033'
                    : serverStatus === 'offline'
                      ? '#ff000033'
                      : '#33333333',
              },
            ]}
          >
            <Ionicons
              name={
                serverStatus === 'healthy'
                  ? 'checkmark-circle'
                  : 'close-circle'
              }
              size={16}
              color={
                serverStatus === 'healthy' ? '#00ff00' : serverStatus === 'offline' ? '#ff0000' : '#888'
              }
            />
            <Text
              style={[
                styles.statusText,
                {
                  color:
                    serverStatus === 'healthy'
                      ? '#00ff00'
                      : serverStatus === 'offline'
                        ? '#ff0000'
                        : '#888',
                },
              ]}
            >
              {serverStatus === 'healthy'
                ? 'Connected'
                : serverStatus === 'offline'
                  ? 'Offline'
                  : 'Checking...'}
            </Text>
          </View>
        </View>
      </View>

      {AVAILABLE_MODELS.map((category) => (
        <View key={category.category} style={styles.categorySection}>
          <Text style={styles.categoryTitle}>{category.category}</Text>
          <FlatList
            scrollEnabled={false}
            data={category.models}
            renderItem={renderModelItem}
            keyExtractor={(item) => item.id}
          />
        </View>
      ))}

      <View style={styles.infoBox}>
        <Ionicons name="information-circle" size={20} color="#00d4ff" />
        <Text style={styles.infoText}>
          Select any model. API models require valid credentials in your server
          configuration. Local models require Ollama running locally.
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
  serverSection: {
    backgroundColor: '#1a1a1a',
    margin: 12,
    borderRadius: 12,
    padding: 16,
    borderColor: '#333',
    borderWidth: 1,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#00d4ff',
    marginBottom: 12,
  },
  serverBox: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 12,
  },
  serverInput: {
    flex: 1,
    backgroundColor: '#2a2a2a',
    color: '#fff',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 13,
  },
  checkButton: {
    width: 40,
    height: 40,
    borderRadius: 8,
    backgroundColor: '#2a2a2a',
    justifyContent: 'center',
    alignItems: 'center',
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  statusLabel: {
    color: '#888',
    fontSize: 12,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 6,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  categorySection: {
    margin: 12,
  },
  categoryTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#00d4ff',
    marginBottom: 8,
  },
  modelItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1a1a1a',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
    borderColor: '#333',
    borderWidth: 1,
  },
  modelItemSelected: {
    borderColor: '#00d4ff',
    backgroundColor: '#1a1a2a',
  },
  modelIconContainer: {
    width: 40,
    height: 40,
    borderRadius: 8,
    backgroundColor: '#2a2a2a',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  modelInfo: {
    flex: 1,
  },
  modelName: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  modelId: {
    color: '#888',
    fontSize: 12,
    marginTop: 2,
  },
  infoBox: {
    backgroundColor: '#1a1a2a',
    margin: 12,
    borderRadius: 8,
    padding: 12,
    borderColor: '#00d4ff33',
    borderWidth: 1,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
  },
  infoText: {
    color: '#aaa',
    fontSize: 12,
    flex: 1,
    lineHeight: 16,
  },
});

export default ModelsScreen;
