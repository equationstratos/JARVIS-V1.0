import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import ChatScreen from './src/screens/ChatScreen';
import ModelsScreen from './src/screens/ModelsScreen';
import SettingsScreen from './src/screens/SettingsScreen';
import { useChatStore } from './src/store/chatStore';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

function ChatStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: '#1a1a1a' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: 'bold' },
      }}
    >
      <Stack.Screen
        name="ChatMain"
        component={ChatScreen}
        options={{ title: 'JARVIS Chat' }}
      />
    </Stack.Navigator>
  );
}

export default function App() {
  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={({ route }) => ({
          headerShown: false,
          tabBarIcon: ({ focused, color, size }) => {
            let iconName;
            if (route.name === 'Chat') {
              iconName = focused ? 'chatbubble' : 'chatbubble-outline';
            } else if (route.name === 'Models') {
              iconName = focused ? 'settings' : 'settings-outline';
            } else if (route.name === 'Settings') {
              iconName = focused ? 'cog' : 'cog-outline';
            }
            return <Ionicons name={iconName} size={size} color={color} />;
          },
          tabBarActiveTintColor: '#00d4ff',
          tabBarInactiveTintColor: '#888',
          tabBarStyle: { backgroundColor: '#1a1a1a', borderTopColor: '#333' },
        })}
      >
        <Tab.Screen
          name="Chat"
          component={ChatStack}
          options={{ title: 'Chat' }}
        />
        <Tab.Screen
          name="Models"
          component={ModelsScreen}
          options={{ title: 'Models' }}
        />
        <Tab.Screen
          name="Settings"
          component={SettingsScreen}
          options={{ title: 'Settings' }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
