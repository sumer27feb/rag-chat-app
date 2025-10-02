import { BrowserRouter as Router, Route, Routes } from "react-router-dom";
import ChatPage from "./components/chat/ChatPage";
import Header from "./components/chat/Header";
import Home from "./Home";

function App() {
  return (
    <Router>
      <div className="flex flex-col flex-1 bg-[#1e1e1e]">
        <Header />
      </div>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/chats/:chat_id" element={<ChatPage />} />
      </Routes>
    </Router>
  );
}

export default App;
