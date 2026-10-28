import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import './index.css';
import { AuthProvider } from './lib/auth';
import { LocationProvider } from './lib/location';
import { SettingsProvider } from './lib/settings';
import CentreDetail from './pages/CentreDetail';
import Dishes from './pages/Dishes';
import Finder from './pages/Finder';
import Home from './pages/Home';
import StallDetail from './pages/StallDetail';
import { Alerts, Profile, ProfileEdit, Saved, SignIn } from './pages/UserPages';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SettingsProvider>
      <AuthProvider>
        <LocationProvider>
          <BrowserRouter>
            <Routes>
              <Route element={<Layout />}>
                <Route index element={<Home />} />
                <Route path="signin" element={<SignIn />} />
                <Route path="setup" element={<ProfileEdit onboarding />} />
                <Route path="finder" element={<Finder />} />
                <Route path="centres/:id" element={<CentreDetail />} />
                <Route path="stalls/:id" element={<StallDetail />} />
                <Route path="dishes" element={<Dishes />} />
                <Route path="saved" element={<Saved />} />
                <Route path="alerts" element={<Alerts />} />
                <Route path="profile" element={<Profile />} />
                <Route path="profile/edit" element={<ProfileEdit />} />
                <Route path="*" element={<p className="py-10 text-center text-stone-500">Page not found.</p>} />
              </Route>
            </Routes>
          </BrowserRouter>
        </LocationProvider>
      </AuthProvider>
    </SettingsProvider>
  </StrictMode>,
);
