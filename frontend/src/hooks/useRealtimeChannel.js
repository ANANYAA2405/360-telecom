import { useEffect } from "react";

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8001/ws";

export function useRealtimeChannel(channel, onEvent) {
  useEffect(() => {
    if (!channel || !onEvent) return undefined;
    const socket = new WebSocket(`${WS_BASE_URL}/${channel}`);
    socket.onmessage = (message) => {
      onEvent(JSON.parse(message.data));
    };
    return () => socket.close();
  }, [channel, onEvent]);
}
