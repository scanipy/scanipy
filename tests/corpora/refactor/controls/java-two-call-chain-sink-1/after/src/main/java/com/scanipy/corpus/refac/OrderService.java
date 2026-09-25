package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input000) throws Exception {
        String left000 = "SELECT * FROM orders WHERE id = '";
        String right000 = "'";
        String value000 = _extracted_value(left000, input000, right000);
        Statement st = conn.createStatement();
        st.executeQuery(value000);
        String secondary = "archived-" + input000;
        String secondValue = _extracted_value(left000, secondary, right000);
        st.executeQuery(secondValue);
    }

    private static String _extracted_value(String prefix, String item, String suffix) {
        String partial = prefix + item;
        String completed = partial + suffix;
        return completed;
    }
}
