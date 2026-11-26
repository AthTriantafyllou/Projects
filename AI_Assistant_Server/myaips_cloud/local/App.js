
import React, { useState } from "react";
import axios from "axios";

function App() {
  const [text, setText] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  // New: upload state
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  // New: learn from URL
  const [url, setUrl] = useState("");
  const [learningUrl, setLearningUrl] = useState(false);

  const handleLearn = async () => {
    if (!text.trim()) return alert("Write something to learn.");
    try {
      await axios.post("/api/learn", { text });
      alert("The system learned the text!");
      setText("");
    } catch (err) {
      alert("Error in /learn: " + (err?.response?.data?.error || err.message));
    }
  };

  const handleAsk = async () => {
    if (!question.trim()) return alert("Write a question.");
    setLoading(true);
    setAnswer("");
    try {
      const res = await axios.post("/api/ask", { question });
      setAnswer(res.data.answer || "—");
    } catch (err) {
      setAnswer("Error communicating with API.");
    } finally {
      setLoading(false);
    }
  };

  // New: upload file → /api/upload (backend θα προστεθεί στο επόμενο βήμα)
  const handleUpload = async () => {
    if (!file) return alert("Select a file to upload.");
    const formData = new FormData();
    formData.append("file", file);

    setUploading(true);
    try {
      const res = await axios.post("/api/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      alert(`ΟΚ: Done of '${file.name}'. Chunks: ${res.data?.chunks ?? "?"}`);
      setFile(null);
    } catch (err) {
      alert("Error in /api/upload: " + (err?.response?.data?.error || err.message));
    } finally {
      setUploading(false);
    }
  };

  // New: learn from URL → /api/learn_url (backend θα προστεθεί στο επόμενο βήμα)
  const handleLearnUrl = async () => {
    if (!url.trim()) return alert("Give a URL.");
    setLearningUrl(true);
    try {
      const res = await axios.post("/api/learn_url", { url });
      alert(`ΟΚ: Done ingest from URL. Chunks: ${res.data?.chunks ?? "?"}`);
      setUrl("");
    } catch (err) {
      alert("Error in /api/learn_url: " + (err?.response?.data?.error || err.message));
    } finally {
      setLearningUrl(false);
    }
  };

  return (
    <div style={{ padding: "40px", fontFamily: "Arial", maxWidth: "700px", margin: "auto" }}>
      <h1>MyAI Pro Assistant</h1>

      {/* Learn raw text */}
      <section style={{ marginTop: 20 }}>
        <h3>Learning texts</h3>
        <textarea
          rows="4"
          value={text}
          onChange={(e) => setText(e.target.value)}
          style={{ width: "100%", marginBottom: "10px" }}
        />
        <button onClick={handleLearn}>Learn</button>
      </section>

      <hr style={{ margin: "30px 0" }} />

      {/* Upload file */}
      <section>
        <h3>Import from file (PDF / DOCX / TXT)</h3>
        <input
          type="file"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          style={{ marginBottom: "10px", display: "block" }}
        />
        <button onClick={handleUpload} disabled={uploading}>
          {uploading ? "Uploading..." : "Upload and Learn"}
        </button>
        {file && <div style={{ marginTop: 8, fontSize: 12 }}>Επιλεγμένο: {file.name}</div>}
      </section>

      <hr style={{ margin: "30px 0" }} />

      {/* Learn from URL */}
      <section>
        <h3>Import from URL (web page)</h3>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://παράδειγμα.gr/άρθρο"
          style={{ width: "100%", marginBottom: "10px" }}
        />
        <button onClick={handleLearnUrl} disabled={learningUrl}>
          {learningUrl ? "Processing..." : "Learn from URL"}
        </button>
      </section>

      <hr style={{ margin: "30px 0" }} />

      {/* Ask */}
      <section>
        <h3>Ask a question</h3>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask something..."
          style={{ width: "100%", marginBottom: "10px" }}
        />
        <button onClick={handleAsk} disabled={loading}>
          {loading ? "Think of..." : "Ask"}
        </button>

        {answer && (
          <div style={{ marginTop: "20px", padding: "10px", background: "#f4f4f4" }}>
            <strong>Απάντηση:</strong> {answer}
          </div>
        )}
      </section>
    </div>
  );
}

export default App;
