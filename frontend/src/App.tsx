import { Route, Routes } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { SettingsPage } from "./pages/SettingsPage";
import { PlannerPage } from "./pages/PlannerPage";
import { RecipesPage } from "./pages/RecipesPage";
import { ShoppingPage } from "./pages/ShoppingPage";
import { RequireAuth } from "./auth/RequireAuth";
import { Navbar } from "./components/Navbar";
import { ProfilesProvider } from "./context/ProfilesContext";
import "./App.css";

export default function App() {
  return (
    <div className="app-shell">
      <ProfilesProvider>
        <Navbar />

        <main>
          <Routes>
            <Route
              path="/"
              element={
                <RequireAuth>
                  <PlannerPage />
                </RequireAuth>
              }
            />
            <Route
              path="/planner"
              element={
                <RequireAuth>
                  <PlannerPage />
                </RequireAuth>
              }
            />
            <Route
              path="/recipes"
              element={
                <RequireAuth>
                  <RecipesPage />
                </RequireAuth>
              }
            />
            <Route
              path="/shopping"
              element={
                <RequireAuth>
                  <ShoppingPage />
                </RequireAuth>
              }
            />
            <Route
              path="/settings"
              element={
                <RequireAuth>
                  <SettingsPage />
                </RequireAuth>
              }
            />

            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            <Route path="*" element={<div className="not-found">404</div>} />
          </Routes>
        </main>
      </ProfilesProvider>
    </div>
  );
}
