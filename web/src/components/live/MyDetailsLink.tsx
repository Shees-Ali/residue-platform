import { Link } from "react-router-dom";
import { UserCog } from "lucide-react";
import { Button } from "@/components/ui/button";

/** Takes the person to the page where they edit their own details. */
export function MyDetailsLink({ label = "Edit my details" }: { label?: string }) {
  return (
    <Button asChild variant="outline" className="h-11">
      <Link to="/settings">
        <UserCog />
        {label}
      </Link>
    </Button>
  );
}
