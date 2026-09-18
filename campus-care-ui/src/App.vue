<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'

const route = useRoute()
const showHeader = computed(() => !route.meta.bare)
</script>

<template>
  <div class="app">
    <AppHeader v-if="showHeader" />
    <RouterView v-slot="{ Component }">
      <component :is="Component" :class="showHeader ? 'with-header' : ''" />
    </RouterView>
  </div>
</template>

<style scoped>
.app {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 有顶栏时，内容区占满剩余高度 */
.with-header {
  flex: 1;
  min-height: 0;
}
</style>
