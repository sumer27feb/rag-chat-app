// src/components/auth/LoginSignupModal.tsx
import React, { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

type Props = { open: boolean; onClose: () => void };

const LoginSignupModal: React.FC<Props> = ({ open, onClose }) => {
  const { loginWithToken } = useAuth();

  // shared inputs
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState(""); // for signup (and your request)
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handleSignup = async () => {
    try {
      setLoading(true);
      setErr(null);
      const { data } = await api.post("/auth/signup", {
        email,
        username,
        password,
      });
      console.log("Signup successful, token:", data);
      await loginWithToken(data.access_token);
      console.log("Signup successful, token:", data);
      onClose();
    } catch (e: any) {
      setErr(e?.response?.data?.detail || "Signup failed");
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async () => {
    try {
      setLoading(true);
      setErr(null);
      // FastAPI OAuth2PasswordRequestForm expects form-encoded body with fields: username (email), password
      const form = new URLSearchParams();
      form.append("username", email);
      form.append("password", password);
      const { data } = await api.post("/auth/login", form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      await loginWithToken(data.access_token);
      console.log("Login successful, token:", data);
      onClose();
    } catch (e: any) {
      setErr(e?.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md bg-[#202123] text-white border border-[#2c2c2c]">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold">Welcome</DialogTitle>
          <p className="text-sm text-gray-400">Log in or create an account</p>
        </DialogHeader>

        <Tabs defaultValue="login" className="w-full">
          <TabsList className="grid grid-cols-2 bg-[#343541]">
            <TabsTrigger value="login" className="text-white">
              Log in
            </TabsTrigger>
            <TabsTrigger value="signup" className="text-white">
              Sign up
            </TabsTrigger>
          </TabsList>

          <TabsContent value="login" className="space-y-3 mt-4">
            <div className="space-y-2">
              <Label className="text-gray-300">Email</Label>
              <Input
                type="email"
                className="bg-[#343541] border-[#2c2c2c] text-white"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-gray-300">Password</Label>
              <Input
                type="password"
                className="bg-[#343541] border-[#2c2c2c] text-white"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>
            {err && <p className="text-red-400 text-sm">{err}</p>}
            <Button className="w-full" onClick={handleLogin} disabled={loading}>
              {loading ? "Signing in..." : "Continue"}
            </Button>
          </TabsContent>

          <TabsContent value="signup" className="space-y-3 mt-4">
            <div className="space-y-2">
              <Label className="text-gray-300">Email</Label>
              <Input
                type="email"
                className="bg-[#343541] border-[#2c2c2c] text-white"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-gray-300">Username</Label>
              <Input
                className="bg-[#343541] border-[#2c2c2c] text-white"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="sumerdev"
              />
              {/* For later: show availability hint here */}
            </div>
            <div className="space-y-2">
              <Label className="text-gray-300">Password</Label>
              <Input
                type="password"
                className="bg-[#343541] border-[#2c2c2c] text-white"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>
            {err && <p className="text-red-400 text-sm">{err}</p>}
            <Button
              className="w-full"
              onClick={handleSignup}
              disabled={loading}
            >
              {loading ? "Creating account..." : "Create account"}
            </Button>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
};

export default LoginSignupModal;
