"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";

const sizeStyles = {
  sm: "w-8 h-8 text-xs",
  md: "w-10 h-10 text-sm",
  lg: "w-14 h-14 text-base",
} as const;

export interface AvatarProps {
  src?: string;
  name: string;
  size?: keyof typeof sizeStyles;
  className?: string;
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
}

export function Avatar({ src, name, size = "md", className }: AvatarProps) {
  const [imgError, setImgError] = useState(false);

  if (src && !imgError) {
    return (
      <img
        src={src}
        alt={name}
        onError={() => setImgError(true)}
        className={cn(
          "rounded-full object-cover border border-primary-container/30",
          sizeStyles[size],
          className,
        )}
      />
    );
  }

  return (
    <div
      className={cn(
        "rounded-full flex items-center justify-center bg-primary/20 text-primary font-bold",
        sizeStyles[size],
        className,
      )}
      title={name}
    >
      {getInitials(name)}
    </div>
  );
}
