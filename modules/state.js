export const state = {
    categoriesConfig: { categories: [], rules: {} },
    trips: [],
    rentalProperties: [],
    transactions: [],
    currentPage: 1,
    limit: 50,
    totalCount: 0,
    totalPages: 1,
    currentFilters: {
        search: "",
        direction: "",
        category: "",
        reviewed: "all",
        startDate: "",
        endDate: "",
        account: "all",
        assignment: "all",
        amount: ""
    },
    hasMore: false,
    plaidLinkHandler: null
};
