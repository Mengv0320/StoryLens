import type { BookListItem } from "../../lib/types";
import BookCard from "./BookCard";

type Props = {
  books: BookListItem[];
  onAction?: (bookId: string, action: string) => void;
};

export default function BookGrid({ books, onAction }: Props) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {books.map((b) => (
        <BookCard key={b.bookId} book={b} onAction={onAction} />
      ))}
    </div>
  );
}
