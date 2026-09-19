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
        direction: "all",
        category: "all",
        reviewed: "all",
        reimbursement: "all",
        month: "",
        startDate: "",
        endDate: "",
        account: "all",
        assignment: "all",
        subcategory: "all",
        amount: ""
    },
    hasMore: false,
    plaidLinkHandler: null
};
