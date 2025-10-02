import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";
import LoginSignupModal from "../auth/LoginSignupModal";
import { useNavigate } from "react-router-dom";

const Header: React.FC = () => {
  const { isLoggedIn, logout } = useAuth();
  const [showLogin, setShowLogin] = useState(false);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout(); // clear auth session
    navigate("/");
  };

  return (
    <div className="w-full bg-[#202123] h-12 flex items-center justify-between px-4 border-b border-[#2c2c2c]">
      {/* App Title */}
      <h1 className="text-white font-semibold text-lg">Sumer's LLM-QA App</h1>

      {/* Auth Buttons */}
      <div>
        {isLoggedIn ? (
          <Button variant="secondary" size="sm" onClick={handleLogout}>
            Logout
          </Button>
        ) : (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowLogin(true)}
          >
            Login / Signup
          </Button>
        )}
      </div>
      {/* Modal */}
      <LoginSignupModal open={showLogin} onClose={() => setShowLogin(false)} />
    </div>
  );
};

export default Header;
