import React, { useState, useEffect } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import "./VoiceAssistant.css";

const VoiceAssistant = () => {
  const [messages, setMessages] = useState([]);
  const [isListening, setIsListening] = useState(false);
  const [chats, setChats] = useState([]);
  const [sessionId, setSessionId] = useState("");
  const [inputText, setInputText] = useState("");

  useEffect(() => {
    fetchChats();
    createNewChat();
  }, []);

  // Create a new chat session
  const createNewChat = async () => {
    try {
      // Stop any ongoing speech when creating new chat
      stopSpeaking();
      
      if (sessionId) {
        await axios.post("http://127.0.0.1:5000/save_chat", { session_id: sessionId });
      }

      const res = await axios.post("http://127.0.0.1:5000/new_chat");
      setSessionId(res.data.session_id);
      setMessages([]);
      setInputText("");
      fetchChats();  // Refresh the chat list
    } catch (error) {
      console.error("Error creating new chat:", error);
    }
  };

  // Fetch all previous chats
  const fetchChats = async () => {
    try {
      const res = await axios.get("http://127.0.0.1:5000/chats");
      setChats(res.data);
    } catch (error) {
      console.error("Error fetching chats:", error);
    }
  };

  // Speech recognition logic
  const startListening = () => {
    const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = "en-US";
    recognition.start();

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onresult = (event) => {
      const text = event.results[0][0].transcript;
      handleSendMessage(text);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.onerror = (event) => {
      console.error("Speech Recognition Error:", event.error);
      setIsListening(false);
    };
  };

  // Stop any ongoing speech
  const stopSpeaking = () => {
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
    }
  };

  // TTS: Speak the bot's response
  const speakResponse = (text) => {
    // Stop any ongoing speech before starting new one
    stopSpeaking();
    const speech = new SpeechSynthesisUtterance(text);
    speech.lang = "en-US";
    speech.rate = 1;
    speech.pitch = 1;
    window.speechSynthesis.speak(speech);
  };

  // Handle sending messages (text + voice)
  const handleSendMessage = async (text) => {
    if (!text.trim()) return;

    const newMessages = [...messages, { sender: "user", text }];
    setMessages(newMessages);
    setInputText("");

    try {
      const res = await axios.post("http://127.0.0.1:5000/process", {
        text,
        session_id: sessionId,
      });

      const botResponse = res.data.bot_response;
      const updatedMessages = [...newMessages, { sender: "bot", text: botResponse }];
      setMessages(updatedMessages);
      speakResponse(botResponse);
    } catch (error) {
      console.error("Error:", error);
    }
  };

  // Handle deleting a specific chat
  const deleteChat = async (chatSessionId, e) => {
    e.stopPropagation(); // Prevent triggering loadChat
    try {
      await axios.post("http://127.0.0.1:5000/delete_chat", { session_id: chatSessionId });
      fetchChats();  // Refresh the sidebar after deleting
      // If we deleted the current chat, clear messages and stop speech
      if (chatSessionId === sessionId) {
        stopSpeaking();
        setMessages([]);
        setSessionId("");
      }
    } catch (error) {
      console.error("Error deleting chat:", error);
    }
  };

  // Load previous chat session
  const loadChat = async (chat) => {
    try {
      // Stop any ongoing speech when switching to another chat
      stopSpeaking();
      
      // Fetch full chat history from the optimized endpoint
      const res = await axios.get(`http://127.0.0.1:5000/chat/${chat.session_id}`);
      setMessages(res.data.chat);
      setSessionId(chat.session_id); // Set the session ID so new messages go to this chat
    } catch (error) {
      console.error("Error loading chat:", error);
    }
  };

  return (
    <div className="container">
      <div className="sidebar">
        <button onClick={createNewChat}>➕ New Chat</button>
        {chats.map((chat, index) => (
          <div key={index} className="chat-item">
            <div onClick={() => loadChat(chat)}>
              <p>{chat.title || `Chat ${index + 1}`}</p>
              <small>{new Date(chat.timestamp).toLocaleString()}</small>
            </div>
            <button className="delete-btn" onClick={(e) => deleteChat(chat.session_id, e)}>🗑️</button>
          </div>
        ))}
      </div>

      <div className="main-content">
        <h2>AURA - AI Voice Assistant</h2>
        <div className="chat-box">
          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.sender}`}>
              {msg.sender === "bot" ? (
                <ReactMarkdown>{msg.text}</ReactMarkdown>
              ) : (
                msg.text
              )}
            </div>
          ))}
        </div>

        <div className="input-container">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Type your message..."
            onKeyPress={(e) => e.key === "Enter" && handleSendMessage(inputText)}
          />
          <button className="send-btn" onClick={() => handleSendMessage(inputText)}>Send</button>
          <button className="mic-btn" onClick={startListening}>
            {isListening ? "🎙️" : "🎤"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default VoiceAssistant;
