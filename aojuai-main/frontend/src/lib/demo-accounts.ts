export type DemoAccount = {
  labelKey: string
  username: string
  password: string
}

export const demoAccounts: DemoAccount[] = [
  { labelKey: 'system.auth.demoAdmin', username: 'admin', password: 'Admin@123456' },
  { labelKey: 'system.auth.demoUser', username: 'test', password: 'Test@123456' },
]
