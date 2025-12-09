<script setup lang="ts">
const { user, logout } = useAuth()

const isOpen = defineModel<boolean>({ default: false })

const handleLogout = () => {
  logout()
  isOpen.value = false
}
</script>

<template>
  <UModal 
    v-model:open="isOpen"
    title="Profile"
    :close="{ color: 'neutral', variant: 'ghost' }"
  >
    <template #body>
      <div v-if="user" class="flex flex-col items-center space-y-4">
        <UUser
          :name="user.name"
          :description="user.email"
          :avatar="{
            src: user.profilePicture,
            alt: user.name,
            size: '2xl'
          }"
        />
      </div>
    </template>

    <template #footer>
      <UButton
        block
        color="error"
        variant="soft"
        icon="i-lucide-log-out"
        @click="handleLogout"
      >
        Sign Out
      </UButton>
    </template>
  </UModal>
</template>
