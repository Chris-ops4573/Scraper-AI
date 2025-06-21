import React, { useState } from 'react';
import axios from 'axios';
import { 
  StyleSheet, Text, View, TextInput, TouchableOpacity, 
  ActivityIndicator, ScrollView, SafeAreaView 
} from 'react-native';
import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';

export default function App() {
  const [input, setInput] = useState('');
  const [response, setResponse] = useState('');
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState<Audio.Recording | null>(null);


  const handleSend = async () => {
    if (!input.trim()) return;
    setLoading(true);
    setResponse('');

    try {
      const res = await axios.post('http://10.0.2.2:8000/chat', { message: input });
      setResponse(res.data.reply);
    } catch (err) {
      console.error(err);
      setResponse('Error connecting to server.');
    }
    setLoading(false);
  };

  const startRecording = async () => {
    try {
      const permission = await Audio.requestPermissionsAsync();
      if (permission.status !== 'granted') {
        console.log('Permission not granted!');
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const newRecording = new Audio.Recording();
      await newRecording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      await newRecording.startAsync();
      setRecording(newRecording);
    } catch (err) {
      console.error('Failed to start recording', err);
    }
  };

  const stopRecording = async () => {
    if(recording){
      try {
        await recording.stopAndUnloadAsync();
        const uri = recording.getURI();
        console.log('Recording stored at', uri);
        setRecording(null);
        await uploadRecording(uri!);
      } catch (err) {
        console.error('Failed to stop recording', err);
      }
    } else{
      console.log("Error: recording is of type:null")
    }
  };

 const uploadRecording = async (uri: string) => {
  setLoading(true);
  setResponse('');

  const formData = new FormData();
  formData.append('audio', {
    uri: uri,
    type: 'audio/m4a',
    name: 'audio.m4a'
  });

  try {
    const res = await fetch('http://10.0.2.2:8000/chat-voice', {
      method: 'POST',
      body: formData,
      headers: {
        'Content-Type': 'multipart/form-data',
      }
    });
    const data = await res.json();
    setResponse(data.reply);
  } catch (err) {
    console.error(err);
    setResponse('Error processing audio.');
  }

  setLoading(false);
};

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>🧠 VR AI Agent</Text>

      <TextInput
        style={styles.input}
        placeholder="Type your query..."
        placeholderTextColor="#777"
        value={input}
        onChangeText={setInput}
      />

      <View style={styles.buttonRow}>
        <TouchableOpacity style={styles.button} onPress={handleSend} disabled={loading}>
          <Text style={styles.buttonText}>Ask</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.voiceButton} 
          onPress={recording ? stopRecording : startRecording}
        >
          <Text style={styles.buttonText}>{recording ? 'Stop 🎙️' : 'Record 🎤'}</Text>
        </TouchableOpacity>
      </View>

      {loading && <ActivityIndicator size="large" color="#00bfff" style={styles.loader} />}

      <TouchableOpacity style={styles.clearButton} onPress={() => { setInput(''); setResponse('') }} disabled={!response}>
        <Text style={styles.clearText}>Clear</Text>
      </TouchableOpacity>

      <ScrollView style={styles.responseContainer}>
        <Text style={styles.response}>{response}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#121212', padding: 20 },
  title: { fontSize: 28, fontWeight: 'bold', color: '#fff', marginBottom: 20, alignSelf: 'center' },
  input: { borderWidth: 1, borderColor: '#333', backgroundColor: '#1e1e1e', color: '#fff', padding: 15, borderRadius: 8, marginBottom: 10 },
  buttonRow: { flexDirection: 'row', justifyContent: 'space-between' },
  button: { flex: 1, marginRight: 10, backgroundColor: '#00bfff', padding: 15, borderRadius: 8, alignItems: 'center' },
  voiceButton: { flex: 1, padding: 15, borderRadius: 8, alignItems: 'center', backgroundColor: '#4CAF50' },
  buttonText: { color: '#121212', fontWeight: 'bold', fontSize: 16 },
  clearButton: { marginTop: 10, padding: 10, borderRadius: 8, alignItems: 'center', backgroundColor: '#333' },
  clearText: { color: '#aaa' },
  responseContainer: { flex: 1, marginTop: 20, backgroundColor: '#1e1e1e', padding: 15, borderRadius: 8 },
  response: { fontSize: 16, color: '#fff' },
  loader: { marginVertical: 20 },
});
