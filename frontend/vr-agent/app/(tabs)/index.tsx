import React from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import SignupScreen from '../../components/SignupScreen';
import LoginScreen from '../../components/LoginScreen';
import MainScreen from '@/components/MainScreen';

const Stack = createStackNavigator();

export default function App() {
  return (
    <Stack.Navigator initialRouteName="Login" screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Signup" component={SignupScreen} />
      <Stack.Screen name="Login" component={LoginScreen} />
      <Stack.Screen name="Main" component={MainScreen} />
    </Stack.Navigator>
  );
}