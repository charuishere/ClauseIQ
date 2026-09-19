import { createContext, useContext, useEffect, useState,type ReactNode } from 'react'
import { getCurrentUser, signOut as amplifySignOut, fetchUserAttributes } from 'aws-amplify/auth'

interface AuthUser {
  userId: string
  username: string
  email?: string
}

interface AuthContextType {
  user: AuthUser | null
  isLoading: boolean
  signOut: () => Promise<void>
  checkUser: () => Promise<void>
}

// 1. We create the empty context
const AuthContext = createContext<AuthContextType | undefined>(undefined)

// 2. We create the Provider which wraps around our entire app
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // useEffect runs the code inside it automatically as soon as the app opens
  useEffect(() => {
    checkUser()
  }, [])

  async function checkUser() {
    try {
      // When a user logs in, Amplify's signIn() saves their session into Local
      // Storage; getCurrentUser()/fetchUserAttributes() read it back from there.
      // (lib/api.ts fetches the actual bearer token itself, per-request --
      // this context only tracks who's logged in for the UI.)
      const currentUser = await getCurrentUser()
      const attributes = await fetchUserAttributes()

      // Save them into React's useState memory boxes
      setUser({
        ...currentUser,
        email: attributes.email
      })
    } catch (err) {
      // If error, it means they are not logged in or the token expired
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }

  async function signOut() {
    // Tell AWS to clear Local Storage
    await amplifySignOut()
    // Tell React to clear the memory box
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, signOut, checkUser }}>
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
