<script setup lang="ts">
const { isAuthenticated, login } = useAuth()

const isOpen = computed({
  get: () => !isAuthenticated.value,
  set: () => {} // Can't close without authentication
})

const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

const handleLogin = async () => {
  if (!email.value || !password.value) {
    error.value = 'Please fill in all fields'
    return
  }

  loading.value = true
  error.value = ''

  const result = await login(email.value, password.value)

  if (!result.success) {
    error.value = result.error || 'Login failed'
    loading.value = false
  } else {
    loading.value = false
    // Modal will close automatically when isAuthenticated becomes true
  }
}

const handleKeyPress = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !loading.value) {
    handleLogin()
  }
}
</script>

<template>
  <UModal 
    v-model:open="isOpen"
    title="Login to RAG Chat"
    description="Enter your credentials to access the chat"
    :dismissible="false"
    :close="false"
  >
    <template #body>
      <div class="space-y-4">
        <UFormGroup label="Email" required>
          <UInput
            v-model="email"
            type="email"
            placeholder="your.email@udf.edu.br"
            size="lg"
            icon="i-lucide-mail"
            :disabled="loading"
            @keypress="handleKeyPress"
          />
        </UFormGroup>

        <UFormGroup label="Password" required>
          <UInput
            v-model="password"
            type="password"
            placeholder="Enter your password"
            size="lg"
            icon="i-lucide-lock"
            :disabled="loading"
            @keypress="handleKeyPress"
          />
        </UFormGroup>

        <UAlert
          v-if="error"
          color="error"
          variant="soft"
          :title="error"
          icon="i-lucide-alert-circle"
        />
      </div>
    </template>

    <template #footer>
      <div class="flex flex-col gap-3 w-full">
        <UButton
          block
          size="lg"
          :loading="loading"
          :disabled="loading || !email || !password"
          @click="handleLogin"
        >
          Sign In
        </UButton>

        <div class="text-xs text-center text-muted">
          Demo credentials available for @udf.edu.br emails
        </div>
      </div>
    </template>
  </UModal>
</template>
