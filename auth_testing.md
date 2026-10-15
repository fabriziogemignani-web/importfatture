# Auth Testing
- Login: POST /api/auth/login {email,password} -> sets httpOnly cookies access_token/refresh_token
- GET /api/auth/me with cookies returns user
- POST /api/auth/refresh renews access cookie
- POST /api/auth/logout clears cookies
- 5 wrong attempts -> 429 lockout 15 min (identifier ip:email in login_attempts)
- No public registration endpoint. Credentials in /app/memory/test_credentials.md
