import clsx from "clsx";
import { Link } from "react-router-dom";

const variants = { primary: "button--primary", secondary: "button--secondary", ghost: "button--ghost", danger: "button--danger" };
const buttonClass = (variant = "primary", className) => clsx("button", variants[variant], className);
export function ButtonLink({ variant = "primary", className, children, ...props }) {
  return <Link className={buttonClass(variant, className)} {...props}>{children}</Link>;
}
export default function Button({ variant = "primary", type = "button", className, children, ...props }) {
  return <button type={type} className={buttonClass(variant, className)} {...props}>{children}</button>;
}
