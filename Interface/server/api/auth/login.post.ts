export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const { email, password } = body

  // Hardcoded users
  const users = [
    {
      email: 'ksartin@udf.edu.br',
      password: 'password123',
      name: 'K. Sartin',
      profilePicture: 'https://ui-avatars.com/api/?name=K+Sartin&background=0D8ABC&color=fff'
    },
    {
      email: 'fmlopes@udf.edu.br',
      password: 'password123',
      name: 'F. M. Lopes',
      profilePicture: 'https://ui-avatars.com/api/?name=F+M+Lopes&background=0D8ABC&color=fff'
    },
    {
      email: 'kerlla.luz@udf.edu.br',
      password: 'password123',
      name: 'Kerlla Luz',
      profilePicture: 'https://ui-avatars.com/api/?name=Kerlla+Luz&background=0D8ABC&color=fff'
    }
  ]

  // Find user
  const user = users.find(u => u.email === email && u.password === password)

  if (!user) {
    throw createError({
      statusCode: 401,
      statusMessage: 'Invalid email or password'
    })
  }

  // Return user data (without password)
  return {
    success: true,
    user: {
      email: user.email,
      name: user.name,
      profilePicture: user.profilePicture
    }
  }
})
