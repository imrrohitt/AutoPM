import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { BRAND } from "@/lib/brand";

const LOGO_ASPECT = 476 / 524;

interface LogoProps {
  /** Visual height in pixels */
  size?: number;
  showText?: boolean;
  href?: string | null;
  className?: string;
  textClassName?: string;
}

export function Logo({
  size = 36,
  showText = true,
  href = "/projects",
  className,
  textClassName,
}: LogoProps) {
  const width = Math.round(size * LOGO_ASPECT);

  const image = (
    <Image
      src={BRAND.logo}
      alt={BRAND.name}
      width={width}
      height={size}
      className={cn("object-contain", className)}
      priority
    />
  );

  const content = (
    <>
      {image}
      {showText && (
        <span
          className={cn(
            "font-semibold tracking-tight text-foreground",
            textClassName
          )}
        >
          {BRAND.name}
        </span>
      )}
    </>
  );

  if (href) {
    return (
      <Link
        href={href}
        className={cn("flex items-center gap-2.5 transition-opacity hover:opacity-90", showText && "gap-2.5")}
      >
        {content}
      </Link>
    );
  }

  return <div className="flex items-center gap-2.5">{content}</div>;
}
