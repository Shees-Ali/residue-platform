import { pkr } from "./common";

test("money from the API is paisa and shows as whole rupees", () => {
  expect(pkr(146_200_000)).toBe("PKR 1,462,000");
  expect(pkr(100)).toBe("PKR 1");
  expect(pkr(0)).toBe("PKR 0");
  expect(pkr(2_500_000_000)).toBe("PKR 25,000,000");
});
