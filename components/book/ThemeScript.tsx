import { THEME_STORAGE_KEY } from '@/lib/site';

/**
 * Runs in <head> before first paint: reads the saved preference
 * ('light' | 'dark', absent = 'system'), sets `.dark` and `color-scheme` on
 * <html>, and records the preference as `data-theme-pref` so the toggle's
 * pressed state is correct without waiting for hydration. <html> carries
 * suppressHydrationWarning because this script changes its attributes.
 * See node_modules/next/dist/docs/01-app/02-guides/preventing-flash-before-hydration.md.
 */
const script = `(function(){try{var d=document.documentElement,p=null;try{p=localStorage.getItem(${JSON.stringify(
  THEME_STORAGE_KEY,
)})}catch(e){}if(p!=='light'&&p!=='dark')p='system';var k=p==='dark'||(p==='system'&&window.matchMedia('(prefers-color-scheme: dark)').matches);d.classList.toggle('dark',k);d.style.colorScheme=k?'dark':'light';d.setAttribute('data-theme-pref',p)}catch(e){}})();`;

export function ThemeScript() {
  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
