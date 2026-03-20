import { Link } from "react-router-dom";
import { Music } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/app/providers/AuthProvider";

export function HomePage() {
  const { user, loading } = useAuth();

  if (loading) {
    return null;
  }

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center p-4">
      <div className="mb-8 flex flex-col items-center gap-4 text-neutral-100">
        <div className="p-4 bg-neutral-900 rounded-2xl border border-neutral-800 shadow-xl">
          <Music className="w-12 h-12 text-indigo-400" />
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight">Hifi OpenSubsonic</h1>
        <p className="text-neutral-400 text-center max-w-sm">
          A high-fidelity API proxy for Tidal. Connect any OpenSubsonic client to your music.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 w-full max-w-sm">
        {user ? (
          <Button asChild className="w-full bg-indigo-600 hover:bg-indigo-700 h-12 text-lg">
            <Link to="/dashboard">Go to Dashboard</Link>
          </Button>
        ) : (
          <>
            <Button
              asChild
              variant="outline"
              className="w-full border-neutral-700 bg-neutral-900 text-neutral-200 hover:bg-neutral-800 h-12 text-lg"
            >
              <Link to="/login">Sign In</Link>
            </Button>
            <Button asChild className="w-full bg-indigo-600 hover:bg-indigo-700 text-white h-12 text-lg">
              <Link to="/register">Register</Link>
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
