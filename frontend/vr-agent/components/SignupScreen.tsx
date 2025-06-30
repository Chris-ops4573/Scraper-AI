import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert } from 'react-native';
import axios from 'axios';

export default function SignupScreen({ navigation }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'doctor' | 'patient'>('doctor');

  const handleSignup = async () => {
    try {
      await axios.post('https://a9da-152-57-122-172.ngrok-free.app/users', {
        username,
        password,
        role,
      });
      Alert.alert('Signup successful', 'You can now log in.', [
        { text: 'OK', onPress: () => navigation.replace('Login') }
      ]);
    } catch (err) {
      Alert.alert('Signup failed', err.response?.data?.detail || 'Unknown error');
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Sign Up</Text>
      <TextInput style={styles.input} placeholder="Username" value={username} onChangeText={setUsername} />
      <TextInput style={styles.input} placeholder="Password" value={password} onChangeText={setPassword} secureTextEntry />
      <View style={styles.roleSwitch}>
        <TouchableOpacity style={[styles.roleButton, role === 'doctor' && styles.roleActive]} onPress={() => setRole('doctor')}>
          <Text style={styles.roleText}>Doctor</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.roleButton, role === 'patient' && styles.roleActive]} onPress={() => setRole('patient')}>
          <Text style={styles.roleText}>Patient</Text>
        </TouchableOpacity>
      </View>
      <TouchableOpacity style={styles.button} onPress={handleSignup}>
        <Text style={styles.buttonText}>Sign Up</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={() => navigation.replace('Login')}>
        <Text style={styles.link}>Already have an account? Login</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#121212', justifyContent: 'center', alignItems: 'center', padding: 20 },
  title: { fontSize: 28, fontWeight: 'bold', color: '#fff', marginBottom: 20 },
  input: { width: '100%', borderWidth: 1, borderColor: '#333', backgroundColor: '#1e1e1e', color: '#fff', padding: 15, borderRadius: 8, marginBottom: 10 },
  roleSwitch: { flexDirection: 'row', marginBottom: 20 },
  roleButton: { padding: 10, marginHorizontal: 10, borderRadius: 8, backgroundColor: '#222' },
  roleActive: { backgroundColor: '#00bfff' },
  roleText: { color: '#fff', fontWeight: 'bold' },
  button: { backgroundColor: '#00bfff', padding: 15, borderRadius: 8, alignItems: 'center', marginTop: 10, width: '100%' },
  buttonText: { color: '#121212', fontWeight: 'bold', fontSize: 16 },
  link: { color: '#00bfff', marginTop: 20 }
});