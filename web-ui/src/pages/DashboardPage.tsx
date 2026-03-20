import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, Copy, Disc3, LogOut } from "lucide-react";

import { useAuth } from "@/app/providers/AuthProvider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";

interface LastfmStatusResponse {
  linked: boolean;
}

interface ApiResponse {
  status: string;
  message?: string;
  url?: string;
}

export function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [lastfmLinked, setLastfmLinked] = useState(false);
  const [isLinking, setIsLinking] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });

  useEffect(() => {
    void checkLastfmStatus();
    void handleLastfmCallback();
  }, []);

  const checkLastfmStatus = async () => {
    try {
      const resp = await fetch("/api/lastfm/status");
      if (resp.ok) {
        const data = (await resp.json()) as LastfmStatusResponse;
        setLastfmLinked(data.linked);
      }
    } catch {
      console.error("Failed to fetch lastfm status");
    }
  };

  const handleLastfmCallback = async () => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");

    if (!token) {
      return;
    }

    setIsLinking(true);
    try {
      const resp = await fetch("/api/lastfm/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const data = (await resp.json()) as ApiResponse;
      if (resp.ok && data.status === "ok") {
        toast({
          title: "Success",
          description: "Last.fm account linked successfully!",
        });
        setLastfmLinked(true);
      } else {
        toast({
          variant: "destructive",
          title: "Error",
          description: data.message || "Failed to link Last.fm",
        });
      }
    } catch {
      toast({
        variant: "destructive",
        title: "Error",
        description: "Network error linking Last.fm",
      });
    } finally {
      setIsLinking(false);
      navigate("/dashboard", { replace: true });
    }
  };

  const handleLastfmConnect = async () => {
    try {
      const callbackObj = new URL(window.location.href);
      callbackObj.search = "";
      const callbackUrl = encodeURIComponent(callbackObj.toString());

      const resp = await fetch(`/api/lastfm/auth-url?callback_url=${callbackUrl}`);
      if (!resp.ok) {
        throw new Error("Failed to get auth URL");
      }

      const data = (await resp.json()) as ApiResponse;
      if (data.status === "ok" && data.url) {
        window.location.href = data.url;
        return;
      }

      toast({
        variant: "destructive",
        title: "Configuration Error",
        description: data.message || "Last.fm API is not configured on the server",
      });
    } catch {
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to connect to Last.fm",
      });
    }
  };

  const handleLastfmDisconnect = async () => {
    try {
      const resp = await fetch("/api/lastfm/unlink", { method: "POST" });
      if (resp.ok) {
        setLastfmLinked(false);
        toast({
          title: "Disconnected",
          description: "Your Last.fm account has been unlinked.",
        });
      }
    } catch {
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to unlink Last.fm",
      });
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  const handleChangePassword = async (e: FormEvent) => {
    e.preventDefault();

    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      toast({
        variant: "destructive",
        title: "Password mismatch",
        description: "New password and confirmation must match.",
      });
      return;
    }

    setIsChangingPassword(true);
    try {
      const resp = await fetch("/api/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: passwordForm.currentPassword,
          new_password: passwordForm.newPassword,
        }),
      });

      const data = (await resp.json()) as ApiResponse;
      if (!resp.ok || data.status !== "ok") {
        toast({
          variant: "destructive",
          title: "Password update failed",
          description: data.message || "Unable to change password",
        });
        return;
      }

      setPasswordForm({ currentPassword: "", newPassword: "", confirmPassword: "" });
      setShowPasswordForm(false);
      toast({
        title: "Password changed",
        description: "Your password has been updated successfully.",
      });
    } catch {
      toast({
        variant: "destructive",
        title: "Network error",
        description: "Could not reach the server.",
      });
    } finally {
      setIsChangingPassword(false);
    }
  };

  const serverUrl = window.location.origin;

  const copyToClipboard = (text: string) => {
    void navigator.clipboard.writeText(text);
  };

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center p-4">
      <Card className="w-full max-w-md bg-neutral-900 border-neutral-800 text-neutral-100 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 p-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            className="text-neutral-400 hover:text-white hover:bg-neutral-800"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Sign Out
          </Button>
        </div>

        <CardHeader className="text-center pt-10 pb-2">
          <div className="mx-auto w-12 h-12 bg-green-500/20 rounded-full flex items-center justify-center mb-4">
            <CheckCircle2 className="w-6 h-6 text-green-500" />
          </div>
          <CardTitle className="text-2xl font-bold bg-gradient-to-br from-white to-neutral-400 bg-clip-text text-transparent">
            Welcome, {user?.username}!
          </CardTitle>
          <CardDescription className="text-neutral-400 mt-2">
            Use these credentials to sign into your OpenSubsonic clients (like Feishin, Tempus, or Narjo).
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4 pt-4">
          <div className="space-y-2 p-3 bg-black/40 rounded-lg border border-neutral-800">
            <Label className="text-neutral-500 text-xs uppercase tracking-wider">Server Address</Label>
            <div className="flex items-center justify-between">
              <code className="text-sm font-mono text-neutral-200 break-all">{serverUrl}</code>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 shrink-0 text-neutral-400 hover:text-white"
                onClick={() => copyToClipboard(serverUrl)}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="space-y-2 p-3 bg-black/40 rounded-lg border border-neutral-800">
            <Label className="text-neutral-500 text-xs uppercase tracking-wider">Username</Label>
            <div className="flex items-center justify-between">
              <code className="text-sm font-mono text-neutral-200">{user?.username}</code>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 shrink-0 text-neutral-400 hover:text-white"
                onClick={() => copyToClipboard(user?.username ?? "")}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="space-y-3 p-3 bg-black/40 rounded-lg border border-neutral-800">
            <Label className="text-neutral-500 text-xs uppercase tracking-wider">Password</Label>
            <p className="text-sm text-neutral-400 italic">Use the same password you used to log in to this dashboard.</p>
            {!showPasswordForm ? (
              <Button
                type="button"
                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white"
                onClick={() => setShowPasswordForm(true)}
              >
                Change Password
              </Button>
            ) : (
              <form className="space-y-3" onSubmit={handleChangePassword}>
                <Input
                  type="password"
                  placeholder="Current password"
                  value={passwordForm.currentPassword}
                  onChange={(e) => setPasswordForm((prev) => ({ ...prev, currentPassword: e.target.value }))}
                  className="bg-neutral-950 border-neutral-800 focus-visible:ring-indigo-500 text-neutral-200"
                />
                <Input
                  type="password"
                  placeholder="New password (min 8 chars)"
                  value={passwordForm.newPassword}
                  onChange={(e) => setPasswordForm((prev) => ({ ...prev, newPassword: e.target.value }))}
                  className="bg-neutral-950 border-neutral-800 focus-visible:ring-indigo-500 text-neutral-200"
                />
                <Input
                  type="password"
                  placeholder="Confirm new password"
                  value={passwordForm.confirmPassword}
                  onChange={(e) => setPasswordForm((prev) => ({ ...prev, confirmPassword: e.target.value }))}
                  className="bg-neutral-950 border-neutral-800 focus-visible:ring-indigo-500 text-neutral-200"
                />
                <div className="flex gap-2">
                  <Button
                    type="submit"
                    disabled={isChangingPassword}
                    className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white"
                  >
                    {isChangingPassword ? "Updating..." : "Update Password"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className="flex-1 border-neutral-700 bg-neutral-900 text-neutral-200 hover:bg-neutral-800"
                    onClick={() => {
                      setShowPasswordForm(false);
                      setPasswordForm({ currentPassword: "", newPassword: "", confirmPassword: "" });
                    }}
                    disabled={isChangingPassword}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            )}
          </div>

          <div className="pt-4 border-t border-neutral-800">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-red-500/10 rounded-lg">
                  <Disc3 className="w-5 h-5 text-red-500" />
                </div>
                <div>
                  <h3 className="font-semibold text-neutral-200">Last.fm Scrobbling</h3>
                  <p className="text-xs text-neutral-400">
                    {lastfmLinked ? "Your account is connected." : "Connect your account to scrobble tracks."}
                  </p>
                </div>
              </div>

              {lastfmLinked ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleLastfmDisconnect}
                  className="border-neutral-700 bg-neutral-900 hover:bg-red-950 hover:text-red-400 hover:border-red-900"
                >
                  Disconnect
                </Button>
              ) : (
                <Button
                  size="sm"
                  onClick={handleLastfmConnect}
                  disabled={isLinking}
                  className="bg-red-600 hover:bg-red-700 text-white"
                >
                  {isLinking ? "Connecting..." : "Connect"}
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
