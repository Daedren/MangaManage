<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router';
</script>

<template>
  <header class="site-header">
    <nav class="site-nav" aria-label="Main navigation">
      <span class="wordmark" aria-label="MangaManage">MM</span>
      <ul class="nav-links" role="list">
        <li><RouterLink to="/" exact-active-class="is-active">Chapters</RouterLink></li>
        <li><RouterLink to="/tasks" active-class="is-active">Tasks</RouterLink></li>
        <li><RouterLink to="/logs" active-class="is-active">Logs</RouterLink></li>
      </ul>
    </nav>
  </header>

  <RouterView />

  <footer class="site-footer" role="contentinfo">
    <span class="footer-rule" aria-hidden="true"></span>
    <p class="footer-line">
      <span class="footer-brand">MangaManage</span>
      <span class="footer-sep" aria-hidden="true">·</span>
      <span class="footer-note">manga archive manager</span>
    </p>
  </footer>
</template>

<style scoped>
/* ─── N9 Edge-aligned nav ─────────────────────────────────────────── */
.site-header {
  width: 100%;
  border-bottom: 1px solid var(--color-rule);
  background: var(--color-paper);
}

.site-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-6);
  max-width: var(--layout-max);
  margin: 0 auto;
  padding: var(--space-4) var(--layout-page-pad);
}

/* Wordmark — mono, small, left-anchored */
.wordmark {
  font-family: var(--font-display);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  letter-spacing: 0.12em;
  color: var(--color-ink);
  text-transform: uppercase;
  user-select: none;
}

/* Nav links — right-aligned, edge-to-edge */
.nav-links {
  display: flex;
  align-items: center;
  gap: var(--space-6);
}

.nav-links a {
  font-family: var(--font-body);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--color-ink-2);
  text-decoration: none;
  padding: var(--space-1) 0;
  border-bottom: 1.5px solid transparent;
  transition: color var(--dur-fast) var(--ease-out),
              border-color var(--dur-fast) var(--ease-out);
}

.nav-links a:hover {
  color: var(--color-ink);
  text-decoration: none;
}

.nav-links a.is-active {
  color: var(--color-accent);
  border-bottom-color: var(--color-accent);
}

.nav-links a:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 3px;
  border-radius: var(--radius-sm);
}

/* ─── Ft2 Inline single-line footer ──────────────────────────────── */
.site-footer {
  width: 100%;
  margin-top: auto;
}

.footer-rule {
  display: block;
  height: 1px;
  background: var(--color-rule);
  width: 100%;
}

.footer-line {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  max-width: var(--layout-max);
  margin: 0 auto;
  padding: var(--space-4) var(--layout-page-pad);
  font-family: var(--font-display);
  font-size: var(--text-xs);
  color: var(--color-ink-3);
  max-width: none;
}

.footer-brand {
  color: var(--color-ink-2);
  font-weight: var(--weight-medium);
  letter-spacing: 0.06em;
}

.footer-sep {
  opacity: 0.4;
}

/* ─── Mobile ────────────────────────────────────────────────────── */
@media (max-width: 480px) {
  .nav-links {
    gap: var(--space-4);
  }
}
</style>
