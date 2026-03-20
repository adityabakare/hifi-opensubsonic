import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AlertCircle, ArrowLeft } from "lucide-react";

import { useAuth } from "@/app/providers/AuthProvider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface RegisterResponse {
  status: string;
  message?: string;
}

export function RegisterPage() {
  const [formData, setFormData] = useState({ username: "", password: "", email: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { checkAuth } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const resp = await fetch("/api/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      const data = (await resp.json()) as RegisterResponse;

      if (!resp.ok || data.status === "error") {
        setError(data.message || "Registration failed");
      } else {
        await checkAuth();
        navigate("/dashboard");
      }
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center p-4 relative">
      <div className="absolute top-4 left-4 sm:top-8 sm:left-8">
        <Button variant="ghost" size="sm" asChild className="text-neutral-400 hover:text-white">
          <Link to="/">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Link>
        </Button>
      </div>
      <Card className="w-full max-w-md bg-neutral-900 border-neutral-800 text-neutral-100 shadow-2xl">
        <CardHeader>
          <CardTitle>Create an Account</CardTitle>
          <CardDescription className="text-neutral-400">Sign up to securely access your music library.</CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-6 bg-red-950/50 border-red-900/50 text-red-400">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                className="bg-neutral-950 border-neutral-800 focus-visible:ring-indigo-500 text-neutral-200"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">
                Email <span className="text-neutral-500 text-xs">(Optional)</span>
              </Label>
              <Input
                id="email"
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="bg-neutral-950 border-neutral-800 focus-visible:ring-indigo-500 text-neutral-200"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="bg-neutral-950 border-neutral-800 focus-visible:ring-indigo-500 text-neutral-200"
              />
            </div>
            <Button type="submit" className="w-full mt-6 bg-indigo-600 hover:bg-indigo-700 text-white" disabled={loading}>
              {loading ? "Creating account..." : "Create Account"}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex justify-center border-t border-neutral-800 pt-6">
          <p className="text-neutral-400 text-sm">
            Already have an account?{" "}
            <Link to="/login" className="text-indigo-400 hover:text-indigo-300 ml-1">
              Sign In
            </Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}
