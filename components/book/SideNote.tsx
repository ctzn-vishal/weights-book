import type { ReactNode } from 'react';

/**
 * A margin note. From xl up it floats into the right margin beside the line
 * where it appears (the Tufte technique: float right, negative margin);
 * below xl it sits inline as an indented small note. A <span>, so it is valid
 * inside a paragraph; it may also stand on its own line between paragraphs.
 * Nothing load-bearing belongs here: a reader on a phone meets it mid-text.
 */
export function SideNote({ children }: { children?: ReactNode }) {
  return (
    <span className="sidenote" role="note">
      {children}
    </span>
  );
}
