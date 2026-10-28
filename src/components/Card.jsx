import clsx from "clsx";
export default function Card({ className, children, ...props }) {
  return <div className={clsx("surface", className)} {...props}>{children}</div>;
}
