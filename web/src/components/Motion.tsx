import { Children, cloneElement, isValidElement, type CSSProperties, type HTMLAttributes, type ReactElement } from "react";

type BoxProps = HTMLAttributes<HTMLElement>;
export function Reveal({ className = "", style, delay = 0, ...props }: BoxProps & { delay?: number }) {
  return <div {...props} className={`motion-reveal ${className}`} style={{ ...style, "--stagger": `${delay}ms` } as CSSProperties} />;
}

/** Clone direct children so links, articles, refs, grid layout and selectors stay intact. */
export function Stagger({ children, className = "", as: Tag = "div", ...props }: BoxProps & { as?: "div" | "ul" | "dl" }) {
  return <Tag {...props} className={`motion-stagger ${className}`}>{Children.map(children, (child, index) => {
    if (!isValidElement(child)) return child;
    const element = child as ReactElement<{ className?: string; style?: CSSProperties }>;
    return cloneElement(element, { className: `${element.props.className ?? ""} motion-reveal`,
      style: { ...element.props.style, "--stagger": `${Math.min(index * 55, 385)}ms` } as CSSProperties });
  })}</Tag>;
}
export function TiltCard(props: BoxProps) { return <div {...props} data-motion-tilt />; }
export function Spotlight(props: BoxProps) { return <div {...props} data-motion-spotlight />; }
export function ParallaxLayer({ className = "", ...props }: BoxProps) { return <div {...props} className={`motion-depth ${className}`} aria-hidden="true" />; }
