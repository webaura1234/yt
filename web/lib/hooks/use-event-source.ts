"use client";

import { useEffect, useRef } from "react";

/**
 * Subscribes to a Server-Sent Events endpoint for as long as `url` is non-null.
 * Reconnects automatically when `url` changes; cleans up on unmount.
 *
 * If the server closes the stream after a terminal event (as the jobs/logs
 * endpoints do), the browser's native EventSource does NOT know to stop - it just
 * keeps auto-reconnecting forever. Pass `stopOn` to explicitly close the connection
 * once a terminal message arrives, instead of relying on that default behavior.
 */
export function useEventSource<T = unknown>(
  url: string | null,
  onMessage: (data: T) => void,
  options?: {
    onError?: (err: Event) => void;
    onOpen?: () => void;
    stopOn?: (data: T) => boolean;
  },
) {
  const onMessageRef = useRef(onMessage);
  const optionsRef = useRef(options);

  useEffect(() => {
    onMessageRef.current = onMessage;
    optionsRef.current = options;
  }, [onMessage, options]);

  useEffect(() => {
    if (!url) return;

    const source = new EventSource(url);
    let stopped = false;

    source.onmessage = (event) => {
      if (stopped) return;
      try {
        const data = JSON.parse(event.data) as T;
        onMessageRef.current(data);
        if (optionsRef.current?.stopOn?.(data)) {
          stopped = true;
          source.close();
        }
      } catch {
        // Malformed payload - ignore rather than crash the stream handler.
      }
    };

    source.onopen = () => optionsRef.current?.onOpen?.();
    source.onerror = (err) => {
      if (!stopped) optionsRef.current?.onError?.(err);
    };

    return () => {
      stopped = true;
      source.close();
    };
  }, [url]);
}
