import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Switch,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useChatStore } from '../store/chatStore';
import { getClient } from '../api/client';

const ChatScreen = () => {
  const {
    messages,
    selectedModel,
    serverUrl,
    isLoading,
    liveMode,
    addMessage,
    setIsLoading,
    updateLastMessage,
    clearMessages,
    setLiveMode,
  } = useChatStore();

  const [inputText, setInputText] = useState('');
  const flatListRef = useRef(null);
  const client = getClient(serverUrl);

  useEffect(() => {
    if (flatListRef.current && messages.length > 0) {
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputText.trim()) return;

    const userMessage = inputText.trim();
    setInputText('');
    addMessage('user', userMessage);
    addMessage('assistant', '');
    setIsLoading(true);

    try {
      if (liveMode) {
        // Stream mode
        const response = await client.chatStream({
          query: userMessage,
          model: selectedModel,
          liveMode: true,
        });

        let fullResponse = '';
        for await (const token of response) {
          if (token !== '[DONE]') {
            fullResponse += token;
            updateLastMessage(fullResponse);
          }
        }
      } else {
        // Standard mode
        const response = await client.chat({
          query: userMessage,
          model: selectedModel,
          liveMode: false,
        });
        updateLastMessage(response.response);
      }
    } catch (error) {
      updateLastMessage(`⚠️ Error: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const renderMessage = ({ item }) => (
    <View
      style={[
        styles.messageBubble,
        item.role === 'user' ? styles.userMessage : styles.assistantMessage,
      ]}
    >
      <Text
        style={[
          styles.messageText,
          item.role === 'user' ? styles.userText : styles.assistantText,
        ]}
      >
        {item.content}
      </Text>
    </View>
  );

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={90}
    >
      <View style={styles.header}>
        <Text style={styles.headerTitle}>🚀 JARVIS CHAT v2.0</Text>
        <View style={styles.liveToggle}>
          <Ionicons name="radio" size={16} color="#00d4ff" />
          <Text style={styles.liveText}>Live</Text>
          <Switch
            value={liveMode}
            onValueChange={setLiveMode}
            trackColor={{ false: '#444', true: '#00d4ff' }}
            thumbColor={liveMode ? '#00d4ff' : '#888'}
          />
        </View>
      </View>

      <FlatList
        ref={flatListRef}
        data={messages}
        renderItem={renderMessage}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.messagesList}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Ionicons name="chatbox-ellipses" size={64} color="#444" />
            <Text style={styles.emptyText}>Start a conversation</Text>
            <Text style={styles.emptySubtext}>Model: {selectedModel}</Text>
          </View>
        }
      />

      {isLoading && (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" color="#00d4ff" />
          <Text style={styles.loadingText}>Thinking...</Text>
        </View>
      )}

      <View style={styles.inputContainer}>
        <TextInput
          style={styles.input}
          placeholder="Ask JARVIS..."
          placeholderTextColor="#666"
          value={inputText}
          onChangeText={setInputText}
          multiline
          maxLength={2000}
          editable={!isLoading}
        />
        <TouchableOpacity
          style={[styles.sendButton, isLoading && styles.sendButtonDisabled]}
          onPress={handleSendMessage}
          disabled={isLoading}
        >
          <Ionicons
            name="send"
            size={20}
            color={isLoading ? '#666' : '#00d4ff'}
          />
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
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
    paddingVertical: 12,
    borderBottomColor: '#333',
    borderBottomWidth: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
  },
  liveToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  liveText: {
    color: '#00d4ff',
    fontWeight: '600',
    fontSize: 12,
  },
  messagesList: {
    flexGrow: 1,
    paddingVertical: 16,
    paddingHorizontal: 12,
  },
  messageBubble: {
    marginVertical: 8,
    borderRadius: 16,
    paddingHorizontal: 12,
    paddingVertical: 10,
    maxWidth: '85%',
  },
  userMessage: {
    alignSelf: 'flex-end',
    backgroundColor: '#00d4ff',
  },
  assistantMessage: {
    alignSelf: 'flex-start',
    backgroundColor: '#1a1a1a',
  },
  messageText: {
    fontSize: 15,
    lineHeight: 20,
  },
  userText: {
    color: '#000',
  },
  assistantText: {
    color: '#fff',
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyText: {
    color: '#888',
    fontSize: 16,
    marginTop: 16,
  },
  emptySubtext: {
    color: '#666',
    fontSize: 12,
    marginTop: 4,
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  loadingText: {
    color: '#888',
    fontSize: 13,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: '#1a1a1a',
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderTopColor: '#333',
    borderTopWidth: 1,
    gap: 8,
  },
  input: {
    flex: 1,
    backgroundColor: '#2a2a2a',
    color: '#fff',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    maxHeight: 100,
    fontSize: 15,
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#1a1a1a',
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendButtonDisabled: {
    opacity: 0.5,
  },
});

export default ChatScreen;
