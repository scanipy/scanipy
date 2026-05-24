// reformatted (no semantic change)

package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {

    private final Connection conn;

    public OrderService(Connection conn) {

        this.conn = conn;
    }

    public void lookup(String p048) throws Exception {

        String query048 = "SELECT * FROM orders WHERE id = '" + p048 + "'";
        Statement st = conn.createStatement();
        st.executeQuery(query048);
    }
}
