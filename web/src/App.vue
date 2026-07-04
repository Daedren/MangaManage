<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router';
</script>

<template>
  <header>
    <nav class="navbar">
      <ul>
        <li><RouterLink to="/">Home</RouterLink></li>
        <li><RouterLink to="/about">About</RouterLink></li>
        <li><RouterLink to="/chapters">Chapters</RouterLink></li>
        <li><RouterLink to="/tasks">Tasks</RouterLink></li>
        <li><RouterLink to="/logs">Logs</RouterLink></li>
      </ul>
    </nav>
  </header>

  <main>
    <RouterView />
  </main>
</template>

<style scoped>
/* Ensure the header spans the full width and stays at the top */
header {
  background-color: #333;
  color: white;
  padding: 1rem 0;
  width: 100%;
}

/* Style the navbar to center items horizontally */
.navbar {
  display: flex;
  justify-content: center; /* Center the navigation items horizontally */
  align-items: center; /* Align items vertically */
  width: 100%;
  box-sizing: border-box;
}

/* Style the list inside the navbar */
.navbar ul {
  padding: 0;
  margin: 0;
  display: flex;
  gap: 1.5rem; /* Add spacing between navigation items */
}

/* Style the links */
.navbar a {
  color: white;
  text-decoration: none;
  font-weight: bold;
}

</style>
