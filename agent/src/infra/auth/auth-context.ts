export interface AuthContext {
  role: 'anon' | 'user' | 'admin';
  principal_id: string;
}
