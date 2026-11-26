import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./App.css";
import showdown from "showdown";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function AssistantSelector({ assistantsList, onSelect }) {
  return (
    <div>
      <h1 className="assistant-title">Choose Your AI Assistant</h1>
      <p className="assistant-subtitle">
        Pick the assistant that best matches your workflow.
      </p>

      <div className="assistant-list">
        {assistantsList.map((a) => (
          <div
            key={a.id}
            className="assistant-card"
            onClick={() => onSelect(a.id)}
          >
            <h3 className="assistant-card-title">{a.name}</h3>
            <p className="assistant-card-desc">{a.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function App() {
  // --- AUTH STATE ---
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [token, setToken] = useState(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [authMode, setAuthMode] = useState("login");
  const [authError, setAuthError] = useState("");
  //const [autoScroll, setAutoScroll] = useState(true); // (αν το χρειαστείς μετά)

  // --- ASSISTANT STATE ---
  const [text, setText] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [url, setUrl] = useState("");
  const [learningUrl, setLearningUrl] = useState(false);
  const chatWindowRef = useRef(null);

  // ===== NEW STATE FOR UI (FRONTEND ONLY) =====
  const [messages, setMessages] = useState([]); // {id, sender: "user" | "assistant", text}
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const [uploadMode, setUploadMode] = useState(null); // null | "pdf" | "url"

  const uploadMenuRef = useRef(null);
  const plusButtonRef = useRef(null);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsRef = useRef(null);
  const settingsButtonRef = useRef(null);

  // --- NEW assistant state ---
  const [assistant, setAssistant] = useState(null);
  const [assistantsList, setAssistantsList] = useState([]);
  const [loadingAssistants, setLoadingAssistants] = useState(true);
  const [assistantModalOpen, setAssistantModalOpen] = useState(false);
  
  // ==== HISTORY ====
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
 // XTRAS
  const [XtrasModalOpen, setXtrasModalOpen] = useState(false);
  // GOOGLE 
  const [googleEnabled, setgoogleEnabled] = useState(false);
  // Modes
  const [modes, setModes] = useState([]);
  const [activeMode, setActiveMode] = useState("general");

  const [chatEnabled, setChatEnabled] = useState(false);
  const [calendarConnected, setCalendarConnected] = useState(false);
  const [gmailConnected, setGmailConnected] = useState(false);

  // --- VOICE RECORDING STATES ---
  const [recording, setRecording] = useState(false);
  const mediaRecorder = useRef(null);
  const audioChunks = useRef([]);

  // --- Textarea ref ---
  const textareaRef = useRef(null);
  
  // -- Calendar eve ---
  const [pendingEvent, setPendingEvent] = useState(null);
  const [showEventConfirm, setShowEventConfirm] = useState(false);

  // === FOR BATCH CALENDAR EVENTS ===
  const [showBatchConfirm, setShowBatchConfirm] = useState(false);
  const [lastSocialPlan, setLastSocialPlan] = useState(null);
  const [batchEvents, setBatchEvents] = useState([]);



//
  const startNewConversation = () => {
	  // Clear UI messages
	  setMessages([]);
	  setActiveConversationId(null);
	  setQuestion("");

	  // Optional: scroll to top
	  if (chatWindowRef.current) {
		chatWindowRef.current.scrollTop = 0;
	  }
  };

  // -------------------------------
  // AUTO LOGIN from localStorage
  // -------------------------------
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");
    const urlEmail = params.get("email");

    if (params.get("calendar_connected") === "1") {
      setCalendarConnected(true);
      setActiveMode("month_planner");
    }

    if (params.get("gmail_connected") === "1") {
      setGmailConnected(true);
      setActiveMode("email_search");
    }

    const gc = params.get("google_calendar_connected");
    if (gc === "1") {
      setCalendarConnected(true);
    }

    if (urlToken) {
      setToken(urlToken);
      setIsLoggedIn(true);
      if (urlEmail) setEmail(urlEmail);

      axios.defaults.headers.common["Authorization"] = `Bearer ${urlToken}`;
      localStorage.setItem("token", urlToken);
      if (urlEmail) localStorage.setItem("email", urlEmail);

      window.history.replaceState({}, document.title, "/");
      return;
    }

    // Fallback: localStorage
    const savedToken = localStorage.getItem("token");
    const savedEmail = localStorage.getItem("email");

    if (savedToken && savedEmail) {
      setToken(savedToken);
      setEmail(savedEmail);
      setIsLoggedIn(true);
      axios.defaults.headers.common["Authorization"] = `Bearer ${savedToken}`;
    }
  }, []);

  // ===== CLICK OUTSIDE TO CLOSE UPLOAD MENU AND SETTINGS MENU =====
  useEffect(() => {
    const handleClickOutside = (event) => {
      //
      // --- Upload Menu Close ---
      //
      if (showUploadMenu) {
        const menu = uploadMenuRef.current;
        const plusBtn = plusButtonRef.current;

        if (
          menu &&
          !menu.contains(event.target) &&
          plusBtn &&
          !plusBtn.contains(event.target)
        ) {
          setShowUploadMenu(false);
          setUploadMode(null);
        }
      }

      //
      // --- Settings Menu Close ---
      //
      if (settingsOpen) {
        const menu = settingsRef.current;
        const btn = settingsButtonRef.current;

        if (
          menu &&
          !menu.contains(event.target) &&
          btn &&
          !btn.contains(event.target)
        ) {
          setSettingsOpen(false);
        }
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showUploadMenu, settingsOpen]);

  // ===== AUTO SCROLL CHAT WINDOW =====
  useEffect(() => {
    const chat = chatWindowRef.current;
    if (!chat) return;

    const isAtBottom =
      chat.scrollHeight - chat.scrollTop - chat.clientHeight < 10;

    if (isAtBottom) {
      chat.scrollTop = chat.scrollHeight;
    }
  }, [messages]);

  // -------------------------------
  // LOAD ASSISTANT AFTER LOGIN + LOAD MODES
  // -------------------------------
  useEffect(() => {
    if (!isLoggedIn || !token) return;

    async function loadAssistant() {
      try {
        setLoadingAssistants(true);

        // 1) Load USER settings (chat mode)
        try {
          const chatRes = await axios.get("/api/user_settings");
          setChatEnabled(chatRes.data.chat_enabled);
        } catch (err) {
          console.error("Error loading user settings", err);
          setChatEnabled(false);
        }

		// Load google settings
        try {
          const googleRes = await axios.get("/api/google_settings");
          setgoogleEnabled(googleRes.data.google_enabled);
        } catch (err) {
          console.error("Error loading user settings", err);
          setgoogleEnabled(false);
        }
		
        // 2) Load assistant
        const res = await axios.get("/api/assistant");
        const myAssistant = res.data.assistant || null;
        setAssistant(myAssistant);

        // 3) ΠΑΝΤΑ φόρτωσε τη λίστα assistants
        await loadAssistantsList();

        // 4) Αν υπάρχει ήδη assistant, φόρτωσε modes
        if (myAssistant) {
          try {
            const modesRes = await axios.get("/api/modes");
            setModes(modesRes.data.modes || []);
          } catch (err) {
            console.error("Error loading modes", err);
          }
        }

        setLoadingAssistants(false);
      } catch (err) {
        console.error("Error loading assistant", err);
        setLoadingAssistants(false);
      }
    }

    loadAssistant();
  }, [isLoggedIn, token]);

  // --- Reset textarea height όταν question γίνεται κενό ---
  useEffect(() => {
    if (question === "" && textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [question]);

  // -------------------------------
  // SELECT ASSISTANT
  // -------------------------------
  const selectAssistant = async (assistantId) => {
    try {
      await axios.post("/api/select_assistant", { assistant_id: assistantId });

      const res = await axios.get("/api/assistant");
      const myAssistant = res.data.assistant;
      setAssistant(myAssistant);

      try {
        const modesRes = await axios.get("/api/modes");
        setModes(modesRes.data.modes || []);
      } catch (err) {
        console.error("Error loading modes after assistant change", err);
      }

      setLoadingAssistants(false);
    } catch (err) {
      alert("Error selecting assistant");
    }
  };

  const loadAssistantsList = async () => {
    try {
      const listRes = await axios.get("/api/assistants");
      setAssistantsList(listRes.data.assistants || []);
    } catch (err) {
      console.error("Error loading assistants list", err);
    }
  };

  // -------------------------------
  // AUTH HANDLERS
  // -------------------------------
  const handleAuth = async () => {
    setAuthError("");

    if (!email || !password) {
      setAuthError("Please fill in email and password.");
      return;
    }

    try {
      const endpoint = authMode === "login" ? "/api/login" : "/api/register";
      const body =
        authMode === "register"
          ? { email, password, name }
          : { email, password };

      const res = await axios.post(endpoint, body);
      const tok = res.data.token;
      if (tok) {
        setToken(tok);
        setIsLoggedIn(true);

        // RESET chat & messages for new user login
        setMessages([]);
        setChatEnabled(false);
        setAssistant(null);
        setAssistantsList([]);
        setModes([]);
        setActiveMode("general");

        axios.defaults.headers.common["Authorization"] = `Bearer ${tok}`;

        localStorage.setItem("token", tok);
        localStorage.setItem("email", email);
      }
    } catch (err) {
      console.error(err);
      setAuthError(
        err?.response?.data?.detail || "Error communicating with server."
      );
    }
  };

const handleLogout = async () => {

	  try {
		  await axios.post("/logout", {}, {
			  headers: { Authorization: `Bearer ${token}` }
		  });
	  } catch (e) {
		  console.log("Logout cleanup failed, but continuing:", e);
	  }

	  
    // AUTH
    setIsLoggedIn(false);
	setGmailConnected(false);
	setCalendarConnected(false);
    setToken(null);
    setEmail("");
    setPassword("");
    delete axios.defaults.headers.common["Authorization"];
    localStorage.removeItem("token");
    localStorage.removeItem("email");

    // FULL RESET STATE
    setAssistant(null);
    setAssistantsList([]);
    setModes([]);
    setActiveMode("general");
    setChatEnabled(false);
	setgoogleEnabled(false);
	setActiveConversationId(null);
	
    setMessages([]);
    setQuestion("");
    setAnswer("");
    setText("");

    setFile(null);
    setUploadMode(null);
    setShowUploadMenu(false);
  };

  const toggleChatMode = async () => {
    try {
      const newValue = !chatEnabled;
      await axios.post("/api/toggle_chat", { enabled: newValue });
      setChatEnabled(newValue);
    } catch (err) {
      alert("Error toggling chat mode.");
    }
  };

  const togglegoogleMode = async () => {
    try {
      const newValue = !googleEnabled;
      await axios.post("/api/toggle_google", { enabled: newValue });
      setgoogleEnabled(newValue);
    } catch (err) {
      alert("Error toggling google mode.");
    }
  };
  
  const connectCalendar = () => {
    const token = localStorage.getItem("token");
    window.location.href = `/google-calendar/connect?token=${token}`;
  };

  const handleWeeklyPlannerClick = () => {
    if (!calendarConnected) {
      connectCalendar();
      return;
    }
    setActiveMode("month_planner");
  };


	const handleBatchCalendarClick = async () => {
		
	  setActiveMode("calendar_social_post_batch");	

	  if (!calendarConnected) {
		connectCalendar();
		return;
	  }

	  if (!lastSocialPlan) {
		// No plan to parse
		setMessages(prev => [
		  ...prev,
		  {
			id: Date.now(),
			sender: "assistant",
			text: "There is no content plan yet. Please generate a plan first."
		  }
		]);
		return;
	  }

	  // ---------------------------------------------------
	  // UI: Show “thinking…”
	  // ---------------------------------------------------
	  setLoading(true);
	  setMessages(prev => [
		...prev,
		{
		  id: Date.now(),
		  sender: "assistant",
		  text: "Processing your plan… extracting calendar events…"
		}
	  ]);

	  // ---------------------------------------------------
	  // CALL BACKEND
	  // ---------------------------------------------------
	  try {
		const res = await axios.post("/api/calendar/parse-plan", {
		  plan: lastSocialPlan
		});

		// === INVALID PLAN ===
		if (!res.data.valid) {
		  setLoading(false);
		  setMessages(prev => [
			...prev,
			{
			  id: Date.now(),
			  sender: "assistant",
			  text: res.data.reason || "I could not extract any events from your plan. Please generate a more detailed one."
			}
		  ]);
		  return;
		}

		// === VALID — SHOW MODAL ===
		setBatchEvents(res.data.events);
		setShowBatchConfirm(true);

	  } catch (err) {
		console.error(err);
		setMessages(prev => [
		  ...prev,
		  {
			id: Date.now(),
			sender: "assistant",
			text: "Error processing your plan."
		  }
		]);

	  } finally {
		setLoading(false); // remove “thinking”
	  }
	};


	

  const connectGmail = () => {
    const token = localStorage.getItem("token");
    window.location.href = `/google-gmail/connect?token=${token}`;
  };

  const handleEmailLookupClick = () => {
    if (!gmailConnected) {
      console.log("Email lookup clicked!");
      connectGmail();
      return;
    }
    setActiveMode("email_search");
  };

  // --- START RECORDING ---
  const startRecording = async () => {
    try {
      const token = localStorage.getItem("token");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder.current = new MediaRecorder(stream);

      audioChunks.current = [];

      mediaRecorder.current.ondataavailable = (e) =>
        audioChunks.current.push(e.data);

      mediaRecorder.current.onstop = async () => {
        const audioBlob = new Blob(audioChunks.current, { type: "audio/webm" });
        const formData = new FormData();
        formData.append("file", audioBlob, "audio.webm");

        const res = await fetch("/api/stt", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        });

        const data = await res.json();
        if (data?.text) {
          setQuestion(data.text);
          // μπορείς αν θέλεις: handleAsk();
        }
      };

      mediaRecorder.current.start();
      setRecording(true);
    } catch (err) {
      console.error("Microphone error:", err);
    }
  };

  // --- STOP RECORDING ---
  const stopRecording = () => {
    if (mediaRecorder.current) mediaRecorder.current.stop();
    setRecording(false);
  };

  // -------------------------------
  // ASSISTANT HANDLERS
  // -------------------------------
  const handleLearn = async (customText) => {
    const content = (customText ?? text).trim();
    if (!content) return alert("Write something to learn.");

    try {
      await axios.post("/api/learn", { text: content });
      alert("The system learned the text!");
      if (customText !== undefined) {
        setQuestion("");
      } else {
        setText("");
      }
    } catch (err) {
      alert("Error in /learn: " + (err?.response?.data?.error || err.message));
    }
  };

	const handleAsk = async () => {
	  const userQuestion = question.trim();
	  if (!userQuestion) return alert("Write a question.");

	  // Clear input immediately
	  setQuestion("");

	  if (textareaRef.current) {
		textareaRef.current.style.height = "auto";
	  }

	  setLoading(true);
	  setAnswer("");

	  // ---------------------------------------
	  // ADD USER MESSAGE
	  // ---------------------------------------
	  setMessages((prev) => [
		...prev,
		{ id: Date.now(), sender: "user", text: userQuestion }
	  ]);

	  try {
		const res = await axios.post("/api/ask", {
		  question: userQuestion,
		  mode: activeMode,
		  conversation_id: activeConversationId,
		});

		if (!activeConversationId && res.data.conversation_id) {
		  setActiveConversationId(res.data.conversation_id);
		}

		const aiAnswer = res.data.answer || "—";
		//console.log("AI RAW ANSWER:", aiAnswer);

		setLastSocialPlan(aiAnswer);
		
		// SPECIAL CALENDAR EVENT HANDLING...
		if (activeMode === "calendar_create_event") {
		  try {
			const parsed = JSON.parse(aiAnswer);

			if (parsed.summary && parsed.start && parsed.end) {
			  setPendingEvent(parsed);
			  setShowEventConfirm(true);

			  // PREVIEW MESSAGE
			  setMessages((prev) => [
				...prev,
				{
				  id: Date.now() + 1,
				  sender: "assistant",
				  text: "I prepared the event details. Please confirm if you want me to add it."
				}
			  ]);

			  setLoading(false);
			  return;
			}
		  } catch (err) {
			// Not JSON → normal flow
		  }
		}

		// === Detect Batch Calendar Events (JSON array) ===
		if (activeMode === "calendar_social_post_batch") {
			try {
				const parsed = JSON.parse(aiAnswer);

				// Check if it's a JSON array of events
				if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].summary) {
					
					setBatchEvents(parsed);
					setShowBatchConfirm(true);

					// assistant preview message
					setMessages((prev) => [
						...prev,
						{
							id: Date.now() + 2,
							sender: "assistant",
							text: "I prepared the posting schedule. Confirm if you want me to add all events to your Google Calendar."
						}
					]);

					setLoading(false);
					return; // STOP normal flow
				}
			} catch (e) {
				// JSON parse failed → normal chat flow
			}
		}

		// ---------------------------------------
		// DEFAULT ASSISTANT MESSAGE
		// ---------------------------------------
		setMessages((prev) => [
		  ...prev,
		  {
			id: Date.now() + 2,
			sender: "assistant",
			text: aiAnswer,
			learned: false
		  }
		]);

	  } catch (err) {
		// ERROR MESSAGE
		setMessages((prev) => [
		  ...prev,
		  {
			id: Date.now(),
			sender: "assistant",
			text: "Error communicating with API."
		  }
		]);
	  } finally {
		setLoading(false);
	  }
	};


  const handleUpload = async () => {
    if (!file) return alert("Select a file to upload.");
    const formData = new FormData();
    formData.append("file", file);

    setUploading(true);
    try {
      const res = await axios.post("/api/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      alert(`Your file "${file.name}" was uploaded. Processing has started in the background.`);
      setFile(null);
      setUploadMode(null);
      setShowUploadMenu(false);
    } catch (err) {
      alert(
        "Error in /api/upload: " +
          (err?.response?.data?.error || err.message)
      );
    } finally {
      setUploading(false);
    }
  };

  const handleLearnUrl = async () => {
    const trimmedUrl = url.trim();
    if (!trimmedUrl) return alert("Give a URL.");
    setLearningUrl(true);
    try {
      const res = await axios.post("/api/learn_url", { url: trimmedUrl });
      alert(`ΟΚ: Done ingest from URL. Chunks: ${res.data?.chunks ?? "?"}`);
      setUrl("");
      setUploadMode(null);
      setShowUploadMenu(false);
    } catch (err) {
      alert(
        "Error in /api/learn_url: " +
          (err?.response?.data?.error || err.message)
      );
    } finally {
      setLearningUrl(false);
    }
  };


	const handleCopy = async (markdownText) => {
	  try {
		// 1) Μετατροπή markdown -> HTML
		const converter = new showdown.Converter({
		  tables: true,
		  simplifiedAutoLink: true,
		  strikethrough: true,
		  tasklists: true,
		});
		const html = converter.makeHtml(markdownText);

		// 2) Φτιάχνουμε ένα Blob τύπου HTML
		const blob = new Blob([html], { type: "text/html" });

		// 3) Κάνουμε write στο clipboard με rich text
		await navigator.clipboard.write([
		  new ClipboardItem({ "text/html": blob })
		]);

		alert("Copied with full formatting!");
	  } catch (err) {
		console.error("Copy error:", err);
		alert("Failed to copy.");
	  }
	};


	const handleShare = async (msg) => {
	  try {
		const res = await axios.post("/api/learn/share", {
		  text: msg.text,
		  message_id: msg.id
		});

		// Copy the public URL to clipboard
		navigator.clipboard.writeText(res.data.share_url);

		alert("Share link copied!");
	  } catch (err) {
		alert("Error sharing message.");
	  }
	};

	const handleLearnFromAssistant = async (msg) => {
	  try {
		const res = await axios.post("/api/learn/assistant", {
		  text: msg.text,
		  message_id: msg.id
		});

		// Update the UI so that this message shows as learned
		setMessages((prev) =>
		  prev.map((m) =>
			m.id === msg.id ? { ...m, learned: true } : m
		  )
		);

		alert("Added to your assistant's knowledge!");

	  } catch (err) {
		alert("Error learning from message.");
	  }
	};


  const loadConversations = async () => {
	  try {
		const res = await axios.get("/api/conversations");
		setConversations(res.data.conversations || []);
	  } catch (err) {
		console.error("Error loading conversations", err);
	  }
  };

	const loadMessagesFromConversation = async (conversationId) => {
	  try {
		const res = await axios.get(`/api/conversations/${conversationId}/messages`);
		const msgs = res.data.messages || [];

		// Convert to frontend format
			const mapped = msgs.map((m) => ({
			  id: m.id,
			  sender: m.role === "user" ? "user" : "assistant",
			  text: m.content,
			  learned: false
			}));

		setMessages(mapped);
		
		// After loading messages, check learned statuses
		const assistantMsgs = mapped.filter((m) => m.sender === "assistant");

		if (assistantMsgs.length > 0) {
		  const ids = assistantMsgs.map((m) => m.id);

		  try {
			const statusRes = await axios.post("/api/learn/status", {
			  message_ids: ids
			});

			const statuses = statusRes.data.statuses || {};

			setMessages((prev) =>
			  prev.map((m) =>
				statuses[m.id] ? { ...m, learned: true } : m
			  )
			);
		  } catch (err) {
			console.error("Error fetching learned statuses:", err);
		  }
		}

		setActiveConversationId(conversationId);

	  } catch (err) {
		console.error("Error loading messages", err);
	  }
	};

	const deleteConversation = async (conversationId) => {
	  if (!window.confirm("Are you sure you want to delete this conversation?")) {
		return;
	  }

	  try {
		await axios.delete(`/api/conversations/${conversationId}`);
		// Refresh list
		loadConversations();
	  } catch (err) {
		console.error("Error deleting conversation", err);
		alert("Failed to delete conversation.");
	  }
	};


  // ------ LOGIN SCREEN ------
  if (!isLoggedIn) {
    return (
      <div className="auth-container">
        <div className="auth-box">
          <h1 className="auth-title">
            {authMode === "login" ? "Welcome Back" : "Create Your Account"}
          </h1>

          <p className="auth-subtitle">
            Your personal AI assistant, powered by your own data.
          </p>

          <div className="auth-form">
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="auth-input"
            />

            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="auth-input"
            />

            {authMode === "register" && (
              <input
                type="text"
                placeholder="Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="auth-input"
              />
            )}

            <button onClick={handleAuth} className="auth-button primary">
              {authMode === "login" ? "Login" : "Register"}
            </button>

            <div className="auth-divider">
              <span>or</span>
            </div>

            <button
              onClick={() => {
                window.location.href = "/api/auth/google/login";
              }}
              className="auth-button google"
            >
              <img
                src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg"
                alt="google"
                className="google-icon"
              />
              Continue with Google
            </button>

            {authError && <div className="auth-error">{authError}</div>}

            <div className="auth-switch">
              {authMode === "login" ? (
                <>
                  No account?{" "}
                  <button
                    className="switch-btn"
                    onClick={() => setAuthMode("register")}
                  >
                    Register
                  </button>
                </>
              ) : (
                <>
                  Have an account?{" "}
                  <button
                    className="switch-btn"
                    onClick={() => setAuthMode("login")}
                  >
                    Login
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ------ ASSISTANT SELECTION ------
  if (isLoggedIn && !assistant && !loadingAssistants) {
    return (
      <div className="assistant-select-container">
        <div className="assistant-select-box">
          <AssistantSelector
            assistantsList={assistantsList}
            onSelect={(id) => selectAssistant(id)}
          />
        </div>
      </div>
    );
  }

	const handleConfirmBatchEvents = async () => {
		if (!batchEvents || batchEvents.length === 0) return;

		try {
			const token = localStorage.getItem("token");

			const res = await axios.post("/api/calendar/batch-create-events", 
				{ events: batchEvents },
				{
					headers: {
						Authorization: `Bearer ${token}`,
					},
				}
			);

			setMessages(prev => [
				...prev,
				{
					id: Date.now(),
					sender: "assistant",
					text: "All events were successfully added to your Google Calendar! 🎉"
				}
			]);

		} catch (err) {
			console.error(err);
			setMessages(prev => [
				...prev,
				{
					id: Date.now(),
					sender: "assistant",
					text: "Failed to add some events to Google Calendar."
				}
			]);
		}

		setBatchEvents([]);
		setShowBatchConfirm(false);
	};
	
	const handleConfirmCalendarEvent = async () => {
		//console.log("🚀 Confirm CALLED");
		//console.log("Pending event:", pendingEvent);
  
	  if (!pendingEvent) return;

	  try {
		const token = localStorage.getItem("token");

		const res = await axios.post("/api/calendar/create-event", pendingEvent, {
		  headers: {
			Authorization: `Bearer ${token}`,
		  },
		});

		// Add assistant message
		setMessages(prev => [
		  ...prev,
		  {
			id: Date.now(),
			sender: "assistant",
			text: "Event successfully added to your Google Calendar!"
		  }
		]);

	  } catch (err) {
		console.error(err);
		setMessages(prev => [
		  ...prev,
		  {
			id: Date.now(),
			sender: "assistant",
			text: "Failed to add event to Google Calendar."
		  }
		]);
	  }
	  setShowEventConfirm(false);
	  setPendingEvent(null);
	};


  // ------ MAIN APP UI ------
  return (
    <div className="app-shell">
      {/* LEFT SIDEBAR */}
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <div className="avatar" />
          <div className="user-info">
            <div className="user-name">{email || "USERNAME"}</div>
            <button className="logout-button" onClick={handleLogout}>
              Logout
            </button>
          </div>
          <button
            className="close-sidebar-button"
            onClick={() => setSidebarOpen(false)}
          >
            ✕
          </button>
        </div>
        <div className="sidebar-divider" />
		{/* CHAT MODE TOGGLE BUTTON */}
		<button
		  className="chat-toggle-button"
		  onClick={toggleChatMode}
		  style={{
			width: "90%",
			margin: "10px auto",
			padding: "10px",
			backgroundColor: chatEnabled ? "#228B22" : "#444",
			color: "white",
			border: "none",
			borderRadius: "6px",
			cursor: "pointer",
			display: "block",
		  }}
		>
		  {chatEnabled ? "Chat Mode: ON" : "Chat Mode: OFF"}
		</button> 
		
        <div className="sidebar-scroll-area">
          <div className="mode-buttons">
		   {modes.map((m) => {
			if (m.mode === "month_planner" && googleEnabled) {
			  return (
				<button
				  key={m.mode}
				  className={`mode-btn ${activeMode === m.mode ? "active" : ""}`}
				  onClick={handleWeeklyPlannerClick}
				>
				  {m.title}
				</button>
			  );
			}
			
			if (m.mode === "email_search" && googleEnabled) {
				return (
					<button
						key={m.mode}
						className={`mode-btn ${activeMode === m.mode ? "active" : ""}`}
						onClick={handleEmailLookupClick}
					>
						{m.title}
					</button>
				);
			}
			
			if (m.mode === "calendar_create_event" && googleEnabled) {
			  return (
				<button
				  key={m.mode}
				  className={`mode-btn ${activeMode === m.mode ? "active" : ""}`}
				  onClick={() => {
					if (!calendarConnected) {
					  connectCalendar();
					  return;
					}

					setActiveMode("calendar_create_event");

					// Add initial assistant message
					setMessages((prev) => [
					  ...prev,
					  {
						id: Date.now(),
						sender: "assistant",
						text: "What event would you like to add to your Google Calendar?"
					  }
					]);
				  }}
				>
				  {m.title}
				</button>
			  );
			}

			if (m.mode === "calendar_social_post_batch" && googleEnabled) {
				  return (
					<button
					  key={m.mode}
					  className={`mode-btn ${activeMode === m.mode ? "active" : ""}`}
					  onClick={handleBatchCalendarClick}
					>
					  {m.title}
					</button>
				  );
				}


			return m.mode === "month_planner" || m.mode === "email_search" || m.mode === "calendar_create_event"
			  ? null
			  : (
				<button
				  key={m.mode}
				  className={`mode-btn ${activeMode === m.mode ? "active" : ""}`}
				  onClick={() => setActiveMode(m.mode)}
				>
				  {m.title}
				</button>
			  );
		  })}
          </div>
        </div>
      </aside>

      {/* RIGHT MAIN PANEL */}
      <main className="main-panel">
        {/* SETTINGS BUTTON */}
        <button
          className="settings-button"
          ref={settingsButtonRef}
          onClick={() => setSettingsOpen(!settingsOpen)}
        >
          ⚙️
        </button>

        {/* SETTINGS MENU */}
        {settingsOpen && (
          <div className="settings-menu" ref={settingsRef}>
            <div className="settings-item">Profile</div>
            <div className="settings-item">Account</div>
            <div
              className="settings-item"
              onClick={() => {
                setSettingsOpen(false);
                setAssistantModalOpen(true);
              }}
            >
              Assistant
            </div>
			<div className="settings-item"
			  onClick={() => {
				setSettingsOpen(false);
				loadConversations();
				setHistoryModalOpen(true);
			  }}
			>History </div>
			<div className="settings-item"
				  onClick={() => {
					setSettingsOpen(false);
					startNewConversation();
				  }}
				> ➕ New Conversation </div>
			<div className="settings-item"
			  onClick={() => {
				setSettingsOpen(false);
				setXtrasModalOpen(true);
			  }}
			>Xtras </div>

            <div className="settings-item">Support</div>
            <div className="settings-item">GDPR Consent</div>
            <div className="settings-item">Contact us</div>
          </div>
        )}

        {/* MOBILE HAMBURGER BUTTON */}
        <button
          className={`hamburger-button ${sidebarOpen ? "hidden" : ""}`}
          onClick={() => setSidebarOpen(true)}
        >
          ☰
        </button>

        {/* Chat window */}
        <div className="chat-window" ref={chatWindowRef}>
          {messages.length === 0 && (
            <div className="chat-placeholder">
              Start by asking a question or teaching your assistant.
            </div>
          )}

  
			{messages.map((msg) => (
			  <div key={msg.id} className="message-wrapper">

				<div
				  className={`message-bubble ${
					msg.sender === "user" ? "message-user" : "message-assistant"
				  }`}
				>
				  <ReactMarkdown remarkPlugins={[remarkGfm]} className="markdown-content">
					{msg.text}
				  </ReactMarkdown>

				  {/* ACTION BUTTONS INSIDE THE BUBBLE (ONLY ASSISTANT) */}
				  {msg.sender === "assistant" && (
					<div className="message-actions">
					  <button
						className="action-btn"
						onClick={() => handleCopy(msg.text)}
						title="Copy"
					  >
						📋
					  </button>

					  <button
						className="action-btn"
						onClick={() => handleShare(msg)}
						title="Share"
					  >
						🔗
					  </button>

					  <button
						className={`action-btn ${msg.learned ? "learned" : ""}`}
						onClick={() => !msg.learned && handleLearnFromAssistant(msg)}
						title={msg.learned ? "Already learned" : "Learn"}
						disabled={msg.learned}
					  >
						⭐
					  </button>
					</div>

				  )}
				</div>

			  </div>
			))}


          {loading && (
            <div className="message-bubble message-assistant thinking-bubble">
              Thinking…
            </div>
          )}
        </div>

        {/* Upload menu / panels */}
        {showUploadMenu && (
          <div className="upload-menu" ref={uploadMenuRef}>
            {/* STEP 1: choose mode */}
            {!uploadMode && (
              <div className="upload-menu-inner">
                <button
                  className="upload-option"
                  onClick={() => setUploadMode("pdf")}
                >
                  Upload File (PDF,Word,txt)
                </button>
                <button
                  className="upload-option"
                  onClick={() => setUploadMode("url")}
                >
                  Upload URL
                </button>
              </div>
            )}

            {/* STEP 2A: URL mode */}
            {uploadMode === "url" && (
              <div className="upload-panel">
                <input
                  type="url"
                  className="upload-input"
                  placeholder="URL link..."
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                />
                <button
                  className="upload-learn-button"
                  onClick={handleLearnUrl}
                  disabled={learningUrl}
                >
                  {learningUrl ? "LEARNING..." : "LEARN"}
                </button>
              </div>
            )}

            {/* STEP 2B: PDF/File mode */}
            {uploadMode === "pdf" && (
              <div className="upload-panel">
                <label className="upload-file-label">
                  <span className="upload-file-button">CHOOSE</span>
                  <input
                    type="file"
                    className="upload-file-input"
                    onChange={(e) =>
                      setFile(e.target.files?.[0] || null)
                    }
                  />
                </label>
                <span className="upload-file-name">
                  {file ? file.name : "No file chosen"}
                </span>
                <button
                  className="upload-learn-button"
                  onClick={handleUpload}
                  disabled={uploading}
                >
                  {uploading ? "UPLOADING..." : "LEARN"}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Bottom input bar */}
        <div className="bottom-bar">
          {/* + button to open upload menu */}
          <button
            className="circle-button plus-button"
            ref={plusButtonRef}
            onClick={() => {
              setShowUploadMenu(true);
              setUploadMode(null);
            }}
          >
            +
          </button>

          {/* Textarea input */}
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            placeholder="Ask or give information"
            value={question}
            onChange={(e) => {
              setQuestion(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = e.target.scrollHeight + "px";
            }}
            rows={1}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleAsk();
              }
            }}
          />
		  
		  {/* MOBILE TOOLBAR (only visible on mobile via CSS) */}
			<div className="mobile-toolbar">
			  <button className="mobile-btn" onClick={() => { setShowUploadMenu(true); setUploadMode(null); }}>
				+
			  </button>

			  {/* Mic */}
			  {!recording ? (
				<button className="mobile-btn" onClick={startRecording}>🎤</button>
			  ) : (
				<button className="mobile-btn recording" onClick={stopRecording}>⏹️</button>
			  )}

			  <button className="mobile-btn ask" onClick={handleAsk}>
				➤
			  </button>

			  <button className="mobile-btn learn" onClick={() => handleLearn(question)}>
				★
			  </button>
			</div>


          {/* 🎤 MICROPHONE BUTTON */}
          {!recording ? (
            <button
              className="circle-button mic-button"
              onClick={startRecording}
              title="Start speaking"
            >
              🎤
            </button>
          ) : (
            <button
              className="circle-button mic-button recording"
              onClick={stopRecording}
              title="Stop recording"
            >
              ⏹️
            </button>
          )}

          {/* Black send (ASK) */}
          <button
            className="send-button ask-button"
            onClick={handleAsk}
            disabled={loading}
            title="Ask"
          >
            {loading ? "…" : "➤"}
          </button>

          {/* Yellow send (LEARN) */}
          <button
            className="send-button learn-button"
            onClick={() => handleLearn(question)}
            title="Learn from this text"
          >
            ★
          </button>
        </div>
      </main>

	{historyModalOpen && (
	  <div
		className="modal-overlay"
		onClick={() => setHistoryModalOpen(false)}
	  >
		<div
		  className="modal-box"
		  onClick={(e) => e.stopPropagation()}
		  style={{ maxWidth: "500px" }}
		>
		  <div className="modal-header">
			<h3>Your Conversations</h3>
			<button
			  className="modal-close"
			  onClick={() => setHistoryModalOpen(false)}
			>
			  ✕
			</button>
		  </div>

		  <div className="modal-content">
			{conversations.length === 0 && (
			  <div style={{ padding: "20px", opacity: 0.7 }}>
				No conversations yet.
			  </div>
			)}

			{conversations.map((c) => (
			  <div
				key={c.id}
				className="assistant-modal-card"
				style={{
				  cursor: "pointer",
				  display: "flex",
				  justifyContent: "space-between",
				  alignItems: "center",
				  padding: "12px",
				}}
			  >
				{/* LEFT SIDE → click to open conversation */}
				<div
				  onClick={() => {
					loadMessagesFromConversation(c.id);
					setHistoryModalOpen(false);
					setActiveConversationId(c.id);
				  }}
				  style={{ flexGrow: 1 }}
				>
				  <div className="assistant-modal-title">
					{c.title || "Untitled Conversation"}
				  </div>
				  <div className="assistant-modal-desc">
					Last updated: {new Date(c.updated_at).toLocaleString()}
				  </div>
				</div>

				{/* RIGHT SIDE → delete button */}
				<button
				  style={{
					marginLeft: "12px",
					background: "#ff4d4d",
					border: "none",
					padding: "6px 10px",
					borderRadius: "6px",
					color: "white",
					cursor: "pointer",
				  }}
				  className="history-delete-btn"
				  onClick={(e) => {
					e.stopPropagation(); // prevent opening conversation
					deleteConversation(c.id);
				  }}
				>
				  🗑
				</button>
			  </div>
			))}
		  </div>
		</div>
	  </div>
	)}


	{XtrasModalOpen && (
	  <div
		className="modal-overlay"
		onClick={() => setXtrasModalOpen(false)}
	  >
		<div
		  className="modal-box"
		  onClick={(e) => e.stopPropagation()}
		  style={{ maxWidth: "500px" }}
		>
		  <div className="modal-header">
			<h3>Your Xtras</h3>
			<button
			  className="modal-close"
			  onClick={() => setXtrasModalOpen(false)}
			>
			  ✕
			</button>
		  </div>

		  <div className="modal-content">
				{/* Google MODE TOGGLE BUTTON */}
				<div className="google-mode-container">
				  <span className="google-mode-label">Google Mode:</span>

				  <div 
					className={`toggle-switch ${googleEnabled ? "on" : ""}`}
					onClick={togglegoogleMode}
				  >
					<div className="toggle-thumb"></div>
				  </div>
				</div>
							
		  </div>
		</div>
	  </div>
	)}
	
	
		{showEventConfirm && pendingEvent && (
	<div className="modal-overlay" onClick={() => setShowEventConfirm(false)}>
	<div className="modal-box" onClick={(e) => e.stopPropagation()}>
	  <div className="modal-header">
		<h3>Confirm Calendar Event</h3>
		<button className="modal-close" onClick={() => setShowEventConfirm(false)}>✕</button>
	  </div>

	  <div className="modal-content">
		<p><strong>Title:</strong> {pendingEvent.summary}</p>
		<p><strong>Start:</strong> {pendingEvent.start}</p>
		<p><strong>End:</strong> {pendingEvent.end}</p>
		{pendingEvent.description && (
		  <p><strong>Description:</strong> {pendingEvent.description}</p>
		)}

		<button
		  className="confirm-button"
		  onClick={handleConfirmCalendarEvent}
		>
		  Confirm
		</button>
	  </div>
	</div>
	</div>
	)}
	
	
	{showBatchConfirm && batchEvents.length > 0 && (
	  <div className="modal-overlay" onClick={() => setShowBatchConfirm(false)}>
		<div className="modal-box" onClick={(e) => e.stopPropagation()}>
		  <div className="modal-header">
			<h3>Import {batchEvents.length} events to Google Calendar?</h3>
			<button className="modal-close" onClick={() => setShowBatchConfirm(false)}>✕</button>
		  </div>

		  <div className="modal-content">
			{batchEvents.map((ev, i) => (
			  <div key={i} style={{ marginBottom: "10px" }}>
				<strong>{ev.summary}</strong><br />
				{ev.start} → {ev.end}
			  </div>
			))}

			<button className="confirm-button" onClick={handleConfirmBatchEvents}>
			  Confirm Import
			</button>
		  </div>
		</div>
	  </div>
	)}


      {assistantModalOpen && (
        <div
          className="modal-overlay"
          onClick={() => setAssistantModalOpen(false)}
        >
          <div
            className="modal-box"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h3>Select Your AI Assistant</h3>
              <button
                className="modal-close"
                onClick={() => setAssistantModalOpen(false)}
              >
                ✕
              </button>
            </div>

            <div className="modal-content">
              {assistantsList.map((a) => (
                <div
                  key={a.id}
                  className={`assistant-modal-card ${
                    assistant?.id === a.id ? "selected" : ""
                  }`}
                  onClick={() => {
                    selectAssistant(a.id);
                    setAssistantModalOpen(false);
                  }}
                >
                  <div className="assistant-modal-title">
                    {a.name}
                    {assistant?.id === a.id && (
                      <span className="assistant-check">✔</span>
                    )}
                  </div>

                  <div className="assistant-modal-desc">
                    {a.description}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
