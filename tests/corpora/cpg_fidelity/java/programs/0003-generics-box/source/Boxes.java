package corpus.cpg.p0003;

import java.util.ArrayList;
import java.util.List;

/** Generics with type erasure and bounded type parameters. */
public final class Boxes {

    static final class Box<T> {
        private final T value;

        Box(T value) {
            this.value = value;
        }

        T get() {
            return value;
        }
    }

    static <T extends Comparable<T>> T max(List<T> items) {
        T best = items.get(0);
        for (T item : items) {
            if (item.compareTo(best) > 0) {
                best = item;
            }
        }
        return best;
    }

    public static void main(String[] args) {
        Box<String> b = new Box<>("hi");
        List<Integer> nums = new ArrayList<>();
        nums.add(3);
        nums.add(7);
        System.out.println(b.get() + max(nums));
    }
}
