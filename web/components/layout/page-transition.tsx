"use client";

import { motion } from "framer-motion";
import { usePathname } from "next/navigation";

// Subtle per-route fade/slide so navigating between dashboard pages doesn't feel
// like an instant, jarring swap. Respects the user's reduced-motion preference
// automatically via the root MotionConfig.
//
// Deliberately NOT wrapped in AnimatePresence: some pages (e.g. the generate
// wizard) run their own internal AnimatePresence for step transitions, and
// nesting AnimatePresence contexts left those inner animations stuck at their
// `initial` state. A plain mount-triggered fade (no exit animation) still
// re-fires on every route change - `key={pathname}` forces a remount - without
// touching how each page animates its own content.
export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <motion.div
      key={pathname}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
