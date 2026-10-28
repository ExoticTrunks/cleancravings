# UC-0.1 Log In (updated)

Replaces UC-0.1 in the Use Case Descriptions document (SC2006_UseCaseDescription). The app signs users in with Google through Supabase Auth only, so the email/password and "Forgot password" steps are removed.

| Field | Value |
|---|---|
| **Use Case ID** | UC-0.1 |
| **Use Case Name** | Log In with Google |
| **Created By** | Jovan Chua |
| **Date Created** | 2026-09-04 |
| **Last Updated By** | _(name)_ |
| **Date Last Updated** | 2026-10-26 |
| **Actor** | Primary: User. Secondary: Google Sign-In (via Supabase Auth) |
| **Description** | Allows a user to sign in with their Google account so they can save a health profile, bookmarks and visits, and receive closure alerts. CleanCravings never sees or stores a password. Browsing centres, stalls and dishes doesn't need an account (FR-0.1). |
| **Preconditions** | 1. The user has a Google account.<br>2. The device has a network connection. |
| **Postconditions** | 1. The user is signed in, and the browser holds a Supabase session that is sent to the backend as a Bearer token.<br>2. On first sign-in, the system creates the user's account record.<br>3. The user's health profile, bookmarks, visit log and alerts are available. |
| **Priority** | High |
| **Frequency of Use** | High |
| **Flow of Events** | 1. User selects "Sign in" in the header, or taps an action that needs an account (e.g. Bookmark, Log a visit).<br>2. System displays the Sign-in screen.<br>3. User selects "Continue with Google".<br>4. System redirects the user to Google through Supabase Auth.<br>5. User chooses a Google account and approves access.<br>6. Supabase Auth returns the user to CleanCravings with a session, which the browser stores.<br>7. Backend verifies the session token and creates the user's account record on first sign-in.<br>8. System opens Home. If the user has no health profile yet, Home prompts them to set one up (UC-1.0). |
| **Alternative Flows** | **0.1.AC.1 Returning session:** at Step 1, if a valid session is already stored, the system signs the user in automatically and skips Steps 2–7.<br>**0.1.AC.2 Continue as guest:** at Step 2, the user selects "Continue as guest". The system returns to Home and the user can browse without an account (FR-0.1). Actions that need an account keep sending them to the Sign-in screen.<br>**0.1.AC.3 Sign out:** from the Profile screen, the user selects "Sign out". The system ends the session and removes the stored session from the device. |
| **Exceptions** | **0.1.EX.1 Google sign-in cancelled:** at Step 5, if the user cancels or denies access, no session is created and the user stays signed out on the Sign-in screen.<br>**0.1.EX.2 Session rejected or expired:** at Step 7 (or later), if the backend can't verify the token, the system treats the user as signed out and asks them to sign in again.<br>**0.1.EX.3 Sign-in service unavailable:** at Step 4, if Google or Supabase Auth can't be reached, sign-in fails and the user can keep browsing as a guest. |
| **Includes** | None |
| **Special Requirements** | 1. No passwords are handled or stored by CleanCravings; credentials stay with Google (NFR-8).<br>2. Signing out must remove the stored session from the device, so a shared device doesn't stay signed in.<br>Traces to: FR-0.1, FR-0.2, NFR-8 |
| **Assumptions** | 1. Users have a Google account.<br>2. The Google provider is enabled in the team's Supabase project, with the app's address in its allowed redirect URLs. |
| **Notes and Issues** | Email/password sign-up (shown in the Lab 1 UI prototype) and the "Forgot password" flow were dropped when the team chose Google sign-in. The old 0.1.AC.2 also pointed to UC-8.0, which is Closure Alerts, not password reset. |
