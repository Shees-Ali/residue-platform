import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { LotForm } from "./LotForm";
import { AdminLots, LiveLabel } from "./lots";

/** Admin: every reported lot, the factory ranking, and a form to add a lot for a farmer. */
export function AdminLotsSection() {
  const [open, setOpen] = useState(false);
  return (
    <section aria-label="Reported lots" className="mb-8">
      <div className="section-title">
        <h2>Reported lots</h2>
        <div className="flex items-center gap-3">
          <LiveLabel />
          <Button size="sm" onClick={() => setOpen(true)}>
            <Plus />
            Add a lot for a farmer
          </Button>
        </div>
      </div>
      <AdminLots />
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="form-dialog">
          <DialogTitle>Add a lot for a farmer</DialogTitle>
          <DialogDescription>
            Same details as a phone call. The farmer is found by phone number, or created.
          </DialogDescription>
          <LotForm mode="admin" onDone={() => setOpen(false)} onCancel={() => setOpen(false)} />
        </DialogContent>
      </Dialog>
    </section>
  );
}
