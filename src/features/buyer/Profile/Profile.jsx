import { toPersianDigits } from "../../../utils/persianFormat";
import { LogOut, Phone, Mail } from "lucide-react";
import { useNavigate } from "react-router-dom";
import Card from "../../../components/Card";
import Button from "../../../components/Button";
import { useAuth } from "../../../hooks/useAuth";

export default function Profile() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <div className="max-w-sm mx-auto flex flex-col gap-4">
      <h1 className="page-title">پروفایل من</h1>
      <Card className="flex flex-col gap-3">
        <div className="flex items-center gap-2 text-ink-600">
          <Phone size={16} className="text-dusty-500" />
          <span dir="ltr">{toPersianDigits(user?.phone)}</span>
        </div>
        {user?.email && (
          <div className="flex items-center gap-2 text-ink-600">
            <Mail size={16} className="text-dusty-500" />
            <span dir="ltr">{user.email}</span>
          </div>
        )}
      </Card>
      <Button variant="ghost" className="flex items-center justify-center gap-2 text-red-500" onClick={handleLogout}>
        <LogOut size={16} /> خروج از حساب
      </Button>
    </div>
  );
}
