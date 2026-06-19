import { createContext, useContext, useEffect, useState,type ReactNode } from 'react'
import { getCurrentUser, fetchAuthSession, signOut as amplifySignOut, fetchUserAttributes } from 'aws-amplify/auth'

interface AuthUser {
  userId: string
  username: string
  email?: string
}

interface AuthContextType {
  user: AuthUser | null
  idToken: string | null
  isLoading: boolean
  signOut: () => Promise<void>
  checkUser: () => Promise<void>
}

// 1. We create the empty context
const AuthContext = createContext<AuthContextType | undefined>(undefined)

// 2. We create the Provider which wraps around our entire app
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [idToken, setIdToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // useEffect runs the code inside it automatically as soon as the app opens
  useEffect(() => {
    checkUser()
  }, [])

  async function checkUser() {
    try {
      // 1. When a user logs in, Amplify's signIn() automatically saves their token into Local Storage.
      // 2. Now, fetchAuthSession() reaches into Local Storage to grab that saved token!
      const currentUser = await getCurrentUser()
      const session = await fetchAuthSession()
      const attributes = await fetchUserAttributes()
      const token = session.tokens?.idToken?.toString() || null
      
      // Save them into React's useState memory boxes
      setUser({
        ...currentUser,
        email: attributes.email
      })
      setIdToken(token)
    } catch (err) {
      // If error, it means they are not logged in or the token expired
      setUser(null)
      setIdToken(null)
    } finally {
      setIsLoading(false)
    }
  }

  async function signOut() {
    // Tell AWS to clear Local Storage
    await amplifySignOut()
    // Tell React to clear the memory boxes
    setUser(null)
    setIdToken(null)
  }

  return (
    <AuthContext.Provider value={{ user, idToken, isLoading, signOut, checkUser }}>
      {children}
    </AuthContext.Provider>
  )
}

// 3. We create a shortcut function so other files can easily read the context
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
