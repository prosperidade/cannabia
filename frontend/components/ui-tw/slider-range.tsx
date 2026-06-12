"use client";

import { cn } from "@/lib/cn";

export interface SliderRangeProps {
  value: number;
  onChange: (val: number) => void;
  min?: number;
  max?: number;
  step?: number;
  label?: string;
  showValue?: boolean;
  className?: string;
}

export function SliderRange({
  value,
  onChange,
  min = 0,
  max = 10,
  step = 0.1,
  label,
  showValue = true,
  className,
}: SliderRangeProps) {
  const markers = Array.from({ length: max - min + 1 }, (_, i) => i + min);

  return (
    <div className={cn("space-y-2", className)}>
      {(label || showValue) && (
        <div className="flex justify-between items-end">
          {label && (
            <label className="block font-headline text-lg font-bold text-on-primary-container uppercase tracking-wider">
              {label}
            </label>
          )}
          {showValue && (
            <span className="text-3xl font-black text-primary font-headline">{value}</span>
          )}
        </div>
      )}
      <div className="relative pt-2">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="slider-range w-full"
        />
        <div className="flex justify-between mt-2 text-[10px] font-bold text-stone-500 tracking-widest uppercase">
          {markers.map((m) => (
            <span key={m}>{m}</span>
          ))}
        </div>
      </div>
      <style jsx>{`
        .slider-range {
          -webkit-appearance: none;
          appearance: none;
          width: 100%;
          background: transparent;
        }
        .slider-range::-webkit-slider-runnable-track {
          width: 100%;
          height: 6px;
          cursor: pointer;
          background: #29522e;
          border-radius: 3px;
        }
        .slider-range::-webkit-slider-thumb {
          height: 20px;
          width: 20px;
          border-radius: 50%;
          background: #a3c93a;
          cursor: pointer;
          -webkit-appearance: none;
          margin-top: -7px;
          box-shadow: 0 0 10px rgba(163, 201, 58, 0.4);
        }
        .slider-range::-moz-range-track {
          width: 100%;
          height: 6px;
          cursor: pointer;
          background: #29522e;
          border-radius: 3px;
        }
        .slider-range::-moz-range-thumb {
          height: 20px;
          width: 20px;
          border-radius: 50%;
          background: #a3c93a;
          cursor: pointer;
          border: none;
          box-shadow: 0 0 10px rgba(163, 201, 58, 0.4);
        }
      `}</style>
    </div>
  );
}
