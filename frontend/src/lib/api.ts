import axios from 'axios'
import { fetchAuthSession } from 'aws-amplify/auth'

// 1. Tell Axios to ALWAYS talk to the AWS API URL we saved in .env.local
const api = axios.create({ 
  baseURL: import.meta.env.VITE_API_BASE_URL 
})

// 2. Interceptor: This intercepts EVERY request just before it leaves the browser.
// It grabs the user's AWS security token and glues it to the request header.
api.interceptors.request.use(async (config) => {
  try {
    const session = await fetchAuthSession()
    const token = session.tokens?.idToken?.toString()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  } catch {
    // If the user isn't logged in, do nothing. Let the request fail with a 401.
  }
  return config
})

export default api
