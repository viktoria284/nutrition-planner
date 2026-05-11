import { Navigate, Route, Routes } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { SettingsPage } from "./pages/SettingsPage";
import { RecipesListPage } from "./pages/RecipesListPage";
import { PublicRecipesPage } from "./pages/PublicRecipesPage";
import { RecipeCreatePage } from "./pages/RecipeCreatePage";
import { RecipeDetailsPage } from "./pages/RecipeDetailsPage";
import { RecipeEditPage } from "./pages/RecipeEditPage";
import { FoodsPage } from "./pages/FoodsPage";
import { FoodDetailsPage } from "./pages/FoodDetailsPage";
import { PlanCreatePage } from "./pages/PlanCreatePage";
import { PlanDetailsPage } from "./pages/PlanDetailsPage";
import { PlanShoppingPage } from "./pages/PlanShoppingPage";
import { PlansListPage } from "./pages/PlansListPage";
import { PlansAutogeneratePage } from "./pages/PlansAutogeneratePage";
import { ShoppingListPage } from "./pages/ShoppingListPage";
import { ShoppingListsPage } from "./pages/ShoppingListsPage";
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
                  <Navigate to="/plans" replace />
                </RequireAuth>
              }
            />
            <Route
              path="/planner"
              element={
                <RequireAuth>
                  <Navigate to="/plans" replace />
                </RequireAuth>
              }
            />
            <Route
              path="/recipes"
              element={
                <RequireAuth>
                  <RecipesListPage />
                </RequireAuth>
              }
            />
            <Route
              path="/recipes/public"
              element={
                <RequireAuth>
                  <PublicRecipesPage />
                </RequireAuth>
              }
            />
            <Route
              path="/recipes/new"
              element={
                <RequireAuth>
                  <RecipeCreatePage />
                </RequireAuth>
              }
            />
            <Route
              path="/recipes/:id"
              element={
                <RequireAuth>
                  <RecipeDetailsPage />
                </RequireAuth>
              }
            />
            <Route
              path="/recipes/:id/edit"
              element={
                <RequireAuth>
                  <RecipeEditPage />
                </RequireAuth>
              }
            />
            <Route
              path="/shopping"
              element={
                <RequireAuth>
                  <Navigate to="/shopping-lists" replace />
                </RequireAuth>
              }
            />
            <Route
              path="/plans"
              element={
                <RequireAuth>
                  <PlansListPage />
                </RequireAuth>
              }
            />
            <Route
              path="/plans/new"
              element={
                <RequireAuth>
                  <PlanCreatePage />
                </RequireAuth>
              }
            />
            <Route
              path="/plans/autogenerate"
              element={
                <RequireAuth>
                  <PlansAutogeneratePage />
                </RequireAuth>
              }
            />
            <Route
              path="/plans/:id"
              element={
                <RequireAuth>
                  <PlanDetailsPage />
                </RequireAuth>
              }
            />
            <Route
              path="/plans/:id/shopping"
              element={
                <RequireAuth>
                  <PlanShoppingPage />
                </RequireAuth>
              }
            />
            <Route
              path="/shopping-lists"
              element={
                <RequireAuth>
                  <ShoppingListsPage />
                </RequireAuth>
              }
            />
            <Route
              path="/shopping-lists/:id"
              element={
                <RequireAuth>
                  <ShoppingListPage />
                </RequireAuth>
              }
            />
            <Route
              path="/foods"
              element={
                <RequireAuth>
                  <FoodsPage />
                </RequireAuth>
              }
            />
            <Route
              path="/foods/:id"
              element={
                <RequireAuth>
                  <FoodDetailsPage />
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
