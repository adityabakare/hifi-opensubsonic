import { BrowserRouter } from "react-router-dom";

import { AppRouter } from "@/app/AppRouter";
import { AuthProvider } from "@/app/providers/AuthProvider";
import { Toaster } from "@/components/ui/toaster";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRouter />
        <Toaster />
      </BrowserRouter>
    </AuthProvider>
  );
}
