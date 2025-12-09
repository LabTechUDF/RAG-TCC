<script setup lang="ts">
const { loggedIn } = useUserSession()
const { user } = useAuth()

const open = ref(false)
const showProfile = ref(false)

watch(loggedIn, () => {
  open.value = false
})

defineShortcuts({
  c: () => {
    navigateTo('/')
  }
})
</script>

<template>
  <UDashboardGroup unit="rem">
    <UDashboardSidebar
      id="default"
      v-model:open="open"
      :min-size="12"
      collapsible
      resizable
      class="bg-elevated/50 !hidden"
    >
      <template #header="{ collapsed }">
        <NuxtLink to="/" class="flex items-end gap-0.5">
          <Logo class="h-8 w-auto shrink-0" />
          <span v-if="!collapsed" class="text-xl font-bold text-highlighted">RAG Chat</span>
        </NuxtLink>

        <div v-if="!collapsed" class="flex items-center gap-1.5 ms-auto">
          <UDashboardSidebarCollapse />
        </div>
      </template>

      <template #default="{ collapsed }">
        <div class="flex flex-col gap-1.5">
          <template v-if="collapsed">
            <UDashboardSidebarCollapse />
          </template>
        </div>

        <div v-if="!collapsed" class="p-4 text-sm text-muted">
          <p>Interface de consulta RAG para documentos jurídicos.</p>
        </div>
      </template>

      <template #footer="{ collapsed }">
        <UButton
          v-if="user && !collapsed"
          block
          color="neutral"
          variant="ghost"
          class="p-2"
          @click="showProfile = true"
        >
          <UUser
            :name="user.name"
            :description="user.email"
            :avatar="{
              src: user.profilePicture,
              alt: user.name,
              size: 'sm'
            }"
            :ui="{ 
              root: 'gap-2', 
              wrapper: 'min-w-0',
              name: 'truncate text-sm font-medium',
              description: 'truncate text-xs'
            }"
          />
        </UButton>
        
        <div v-if="!collapsed" class="text-xs text-muted p-2 text-center">
          RAG-TCC © 2024
        </div>
      </template>
    </UDashboardSidebar>

    <slot />
    
    <ProfileModal v-model="showProfile" />
  </UDashboardGroup>
</template>
